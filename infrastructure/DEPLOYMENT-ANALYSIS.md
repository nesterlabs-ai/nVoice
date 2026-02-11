# NesterAI Deployment Analysis

## Current Architecture: AWS Lightsail

| Component | Config | Monthly Cost |
|-----------|--------|-------------|
| Lightsail instance | medium_3_0 (4GB RAM, 2 vCPU x86, 80GB SSD) | ~$20 |
| ECR (2 repos) | Backend + Frontend images | ~$1 |
| Secrets Manager | 2 secrets | ~$1 |
| CloudWatch Logs | 30-day retention | ~$1-3 |
| **Total** | | **~$23-25/mo** |

**Services:** Backend (FastAPI + CPU-only PyTorch), Frontend (Nginx), Caddy (reverse proxy, auto-HTTPS)

**CI/CD:** GitHub Actions -> ECR -> SSH deploy to Lightsail

**IaC:** AWS CDK (Python) with Custom Resources for Lightsail SDK calls

---

## Performance Bottleneck: Emotion Detection

**Observed:** 5-7s on Lightsail vs 1-2s on local Mac ARM Silicon

### Root Cause Analysis

| Factor | Lightsail (2 vCPU x86) | Mac ARM | Impact |
|--------|----------------------|---------|--------|
| wav2vec2 transformer inference (12 layers, FP32) | 1,000-1,500ms | 150-300ms | **Primary bottleneck (70%)** |
| Memory pressure / swap at 4GB | Likely swapping at peak | 16GB+ headroom | +500ms |
| `torch.set_num_threads(2)` | Limited to 2 cores | 8+ cores | 4x fewer threads |
| GC pauses (every 10 inferences) | 50-200ms | Negligible | Periodic spikes |

### INT8 Quantization (Not Viable)

INT8 quantization was evaluated and **intentionally disabled** because it significantly degrades emotion detection accuracy. The wav2vec2 model's regression outputs (arousal, dominance, valence) lose precision with INT8, making the emotion mapping unreliable.

### Pipeline Latency Breakdown

| Stage | Lightsail (2 vCPU x86) | Mac ARM |
|-------|----------------------|---------|
| Audio preprocessing | 50-100ms | 20-50ms |
| Feature extraction (wav2vec2) | 200-300ms | 50-100ms |
| **Transformer inference (12 layers)** | **1,000-1,500ms** | **150-300ms** |
| Mapping + fusion | 50-100ms | 20-50ms |
| LLM text sentiment (Groq API) | 100-200ms | 100-200ms |
| **Total** | **1,400-2,200ms** | **350-700ms** |

---

## Known Lightsail Limitations

1. **Cross-account IAM** - Instance role (AWS account 790779513465) can't access customer resources (account 196061557238). Workaround: IAM user credentials stored in Secrets Manager, manually configured via `aws configure`.
2. **No IAM instance profiles** - Docker daemon needs credentials injected via systemd override for CloudWatch Logs.
3. **No auto-scaling** - Single instance, manual scaling only.
4. **User-data runs once** - CDK user-data only executes on instance creation, not updates. Config synced via CI/CD separately.

---

## Alternative Deployment Options

### Tier 1: Budget VPS Providers

| Provider | Plan | Specs | Cost/mo | Migration |
|----------|------|-------|---------|-----------|
| **Hetzner CX32** | Shared | 4 vCPU, 8GB RAM, 80GB SSD | **$7.50** | Low |
| **Hetzner CCX23** | Dedicated | 4 vCPU, 16GB RAM | ~$28 | Low |
| OVHcloud VPS-1 | Shared | 4 vCPU, 8GB RAM, 75GB SSD | ~$4.20 | Low |

**Pros:** 2-4x specs at lower cost, Docker Compose works as-is, Caddy portable
**Cons:** No AWS ecosystem (ECR, Secrets Manager, CloudWatch), need external logging

### Tier 2: AWS Alternatives

| Plan | Specs | Cost/mo | IAM | Notes |
|------|-------|---------|-----|-------|
| EC2 t3a.medium (x86) | 2 vCPU, 4GB RAM | ~$35 | Native | Same CPU perf, solves IAM |
| EC2 t3a.large (x86) | 2 vCPU, 8GB RAM | ~$55 | Native | No swap pressure |
| **EC2 t4g.medium (ARM)** | 2 vCPU, 4GB RAM | **~$25** | Native | ARM = closer to Mac perf |
| **EC2 t4g.large (ARM)** | 2 vCPU, 8GB RAM | **~$49** | Native | Best balance |
| EC2 c7g.medium (ARM compute-opt) | 1 vCPU, 2GB RAM | ~$27 | Native | Best single-core ARM |

### Tier 3: PaaS

| Platform | Specs | Cost/mo | Notes |
|----------|-------|---------|-------|
| Fly.io shared-cpu-2x | 2 CPU, 4GB | ~$23 | Global edge, WebSocket support |
| Coolify + Hetzner CX32 | 4 vCPU, 8GB | ~$7.50 | Self-hosted PaaS |
| Railway | 2 vCPU, 4GB | ~$80 | Too expensive |
| Render | 2 CPU, 4GB | ~$85 | Too expensive |

### Tier 4: Kubernetes (Overkill)

| Option | Cost/mo | Notes |
|--------|---------|-------|
| EKS + Fargate | ~$129 | Overkill for 3 containers |
| k3s on VPS | VPS cost | High migration effort |

### Disqualified

- **AWS App Runner**: No WebSocket support

---

## Recommended Path: AWS Graviton (EC2)

**Why:** ARM architecture (like Mac Silicon), native IAM, same AWS ecosystem, eliminates all Lightsail workarounds

### Graviton2 (t4g) vs Graviton3 (c7g)

| Feature | t4g (Graviton2) | c7g (Graviton3) |
|---------|----------------|----------------|
| bfloat16 fast math | No | **Yes (2x SIMD bandwidth)** |
| ML performance | Good | **Up to 3x better** |
| `torch.compile()` speedup | ~1.3x | **Up to 2x** |
| CPU model | Burstable (credits) | **Fixed (full CPU always)** |
| Best for | General workloads | **ML inference** |

**Critical:** t4g is burstable. wav2vec2 inference will burn through CPU credits during active conversations, causing surplus charges ($0.04/vCPU-hour above baseline).

### Instance Comparison

| Instance | Specs | On-demand | 1yr RI | Emotion Detection (est.) | Notes |
|----------|-------|-----------|--------|--------------------------|-------|
| t4g.medium | 2 vCPU Grav2, 4GB | ~$31/mo* | ~$27/mo* | ~3-4s | Credit risk, may swap |
| t4g.large | 2 vCPU Grav2, 8GB | ~$55/mo* | ~$37/mo* | ~2-3s | No swap, still no bfloat16 |
| **c7g.large** | **2 vCPU Grav3, 4GB** | **~$59/mo*** | **~$45/mo*** | **~1-2s** | **Best ML perf, no credit risk** |

*Includes EBS gp3 30GB ($2.40) + Elastic IP ($3.60)

### Graviton3 PyTorch Optimizations

Environment variables to set in docker-compose or Dockerfile:

```bash
DNNL_DEFAULT_FPMATH_MODE=BF16      # bfloat16 fast math (Graviton3 only)
LRU_CACHE_CAPACITY=1024            # Cache oneDNN primitives
THP_MEM_ALLOC_ENABLE=1             # Transparent Huge Pages for large tensors
OMP_NUM_THREADS=2                   # Match vCPU count
OMP_PROC_BIND=false
OMP_PLACES=cores
```

Additionally, `torch.compile()` can give up to 2x speedup on Graviton3:
```python
model = torch.compile(model)
```

### ONNX Runtime Alternative

Converting wav2vec2 to ONNX format with ONNX Runtime on Graviton3 provides:
- Up to 65% improvement for FP32 inference
- Up to 30% for INT8 quantized inference
- KleidiAI integration: 28-51% uplift on Graviton3

### PyTorch ARM64 Compatibility

- Native arm64 pip wheels since PyTorch 2.0
- HuggingFace Transformers / wav2vec2 works without code changes
- CPU-only install: `pip install torch --index-url https://download.pytorch.org/whl/cpu`
- AWS Deep Learning Container available:
  ```
  763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-inference-arm64:2.6.0-cpu-py312-ubuntu22.04-ec2
  ```

### Docker ARM64 Builds in CI/CD

**QEMU emulation is 10-30x slower** (2min build -> 30-60min). Use native ARM64 runners instead:

```yaml
build-backend:
  runs-on: ubuntu-24.04-arm   # GitHub native ARM64 runner (GA since 2025)
  steps:
    - uses: docker/build-push-action@v5
      with:
        platforms: linux/arm64  # No QEMU needed
```

Free for public repos, available on Team/Enterprise plans for private repos.

### CDK Migration: Lightsail -> EC2

Moving to EC2 eliminates the entire cross-account workaround:

| Removed (Lightsail) | Replaced By (EC2) |
|---------------------|-------------------|
| `LightsailCustomResource` (270+ lines SDK calls) | `aws_ec2.Instance` (native CDK L2) |
| `EcrCredentials` (IAM user + stored keys) | `aws_iam.Role` (instance profile) |
| Manual `aws configure` on instance | Automatic via instance role |
| Docker daemon systemd credential hack | Native `awslogs` driver |
| Lightsail firewall via SDK | `aws_ec2.SecurityGroup` |

**Kept unchanged:** `NesterECR`, `NesterSecrets`, `NesterCloudWatchLogs`

### DNS Impact

Lightsail Static IPs **cannot transfer** to EC2 Elastic IPs. Migration requires:
1. Allocate new Elastic IP
2. Update `ai.nesterlabs.com` DNS to new IP
3. Short downtime during DNS propagation (mitigate with low TTL before migration)

### Migration Effort: Medium

| Task | Effort |
|------|--------|
| New CDK stack with EC2 constructs | Medium (replace ~400 lines) |
| Update Dockerfile for `linux/arm64` | Low (base images have arm64 variants) |
| Update CI/CD for ARM64 builds | Low (change `runs-on` + `platforms`) |
| Add Graviton env vars to docker-compose | Low |
| DNS cutover | Low |
| Test wav2vec2 on ARM64 | Medium (validate accuracy) |

---

## Graviton Test Deployment (Implemented)

A parallel EC2 Graviton (ARM64) deployment has been created alongside the existing Lightsail stack.

### Setup

```bash
# 1. Create EC2 key pair
aws ec2 create-key-pair --key-name nester-graviton-test \
  --query KeyMaterial --output text > ~/.ssh/nester-graviton-test.pem
chmod 400 ~/.ssh/nester-graviton-test.pem

# 2. Update infrastructure/config/graviton-test.yaml with key_pair_name

# 3. Deploy CDK stack
cd infrastructure
cdk deploy -c environment=graviton-test

# 4. Add GitHub secrets: GRAVITON_HOST, GRAVITON_SSH_KEY
# 5. Create and push graviton-test branch
```

### Architecture

| Component | Lightsail (main) | Graviton (graviton-test branch) |
|-----------|-----------------|-------------------------------|
| Compute | Lightsail medium_3_0 (x86) | EC2 t4g.small (ARM64) |
| Auth | IAM user + stored credentials | IAM instance role (automatic) |
| ECR | nester-ai-dev-* (x86) | nester-ai-graviton-test-* (ARM64) |
| Secrets | nester/dev/api-keys | Same (shared) |
| Logs | /nester-ai/dev | /nester-ai/graviton-test |
| CI/CD | deploy-aws.yml (ubuntu-latest) | deploy-graviton.yml (ubuntu-24.04-arm) |
| Domain | ai.nesterlabs.com | IP-based or graviton-test.nesterlabs.com |

### Key Files

- `infrastructure/stacks/ec2_graviton_stack.py` - CDK stack
- `infrastructure/components/ec2_graviton.py` - EC2 construct with user data
- `infrastructure/config/graviton-test.yaml` - Environment config
- `.github/workflows/deploy-graviton.yml` - ARM64 CI/CD
- `deployment/docker/docker-compose.graviton.yml` - Docker compose with Graviton optimizations

---

## Document History

- 2026-02-11: Added Graviton test deployment (EC2 t4g, parallel stack)
- 2026-02-06: Initial analysis, Graviton deep dive