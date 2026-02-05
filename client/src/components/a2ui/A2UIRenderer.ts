/**
 * A2UI Renderer for Nester AI Voice Assistant
 *
 * Renders A2UI visual components into DOM elements based on template type.
 * Supports all A2UI v1 template formats.
 */

import type {
  A2UIDocument,
  A2UITemplateType,
  SimpleCardProps,
  TemplateGridProps,
  TimelineProps,
  ContactCardProps,
  ComparisonChartProps,
  StatsFlowLayoutProps,
  TeamFlipCardsProps,
  ServiceHoverRevealProps,
  MagazineHeroProps,
  FAQAccordionProps,
  ImageGalleryProps,
  VideoGalleryProps,
} from '../../types/a2ui';

/**
 * A2UI Renderer class - renders A2UI documents to DOM elements
 */
export class A2UIRenderer {
  private container: HTMLElement;

  constructor(containerId: string) {
    console.log('='.repeat(60));
    console.log('🎨 [A2UI] A2UIRenderer INITIALIZING');
    console.log(`   Container ID: ${containerId}`);
    
    const element = document.getElementById(containerId);
    if (!element) {
      console.error(`❌ [A2UI] Container element NOT FOUND: ${containerId}`);
      throw new Error(`A2UI container element not found: ${containerId}`);
    }
    this.container = element;
    console.log('✅ [A2UI] A2UIRenderer initialized successfully');
    console.log('='.repeat(60));
  }

  /**
   * Render an A2UI document
   */
  render(doc: A2UIDocument): void {
    console.log('='.repeat(60));
    console.log('🎨 [A2UI] RENDER CALLED');
    console.log('   Document:', doc);
    
    if (!doc || !doc.root) {
      console.warn('⚠️ [A2UI] Invalid document - missing doc or doc.root');
      return;
    }

    const templateType = doc.root.type;
    const props = doc.root.props;
    const metadata = doc._metadata;

    console.log(`📋 [A2UI] Template Type: ${templateType}`);
    console.log(`📊 [A2UI] Tier: ${metadata?.tier_name || 'unknown'}`);
    console.log('📝 [A2UI] Props:', props);

    // Clear previous content
    this.container.innerHTML = '';

    // Create wrapper with animation
    const wrapper = document.createElement('div');
    wrapper.className = 'a2ui-wrapper a2ui-fade-in';

    // Route to appropriate renderer
    switch (templateType) {
      case 'simple-card':
        wrapper.appendChild(this.renderSimpleCard(props as SimpleCardProps));
        break;
      case 'template-grid':
        wrapper.appendChild(this.renderTemplateGrid(props as TemplateGridProps));
        break;
      case 'timeline':
        wrapper.appendChild(this.renderTimeline(props as TimelineProps));
        break;
      case 'contact-card':
        wrapper.appendChild(this.renderContactCard(props as ContactCardProps));
        break;
      case 'comparison-chart':
        wrapper.appendChild(this.renderComparisonChart(props as ComparisonChartProps));
        break;
      case 'stats-flow-layout':
        wrapper.appendChild(this.renderStatsFlowLayout(props as StatsFlowLayoutProps));
        break;
      case 'team-flip-cards':
        wrapper.appendChild(this.renderTeamFlipCards(props as TeamFlipCardsProps));
        break;
      case 'service-hover-reveal':
        wrapper.appendChild(this.renderServiceHoverReveal(props as ServiceHoverRevealProps));
        break;
      case 'magazine-hero':
        wrapper.appendChild(this.renderMagazineHero(props as MagazineHeroProps));
        break;
      case 'faq-accordion':
        wrapper.appendChild(this.renderFAQAccordion(props as FAQAccordionProps));
        break;
      case 'image-gallery':
        wrapper.appendChild(this.renderImageGallery(props as ImageGalleryProps));
        break;
      case 'video-gallery':
        wrapper.appendChild(this.renderVideoGallery(props as VideoGalleryProps));
        break;
      default:
        wrapper.appendChild(this.renderFallback(props));
    }

    // Add metadata badge
    if (doc._metadata) {
      const badge = document.createElement('div');
      badge.className = 'a2ui-tier-badge';
      badge.textContent = doc._metadata.tier_name;
      wrapper.appendChild(badge);
      console.log(`🏷️ [A2UI] Added tier badge: ${doc._metadata.tier_name}`);
    }

    this.container.appendChild(wrapper);
    console.log('✅ [A2UI] Render complete - element added to DOM');
    console.log('='.repeat(60));
  }

  /**
   * Clear the rendered content
   */
  clear(): void {
    console.log('🧹 [A2UI] Clearing container');
    this.container.innerHTML = '';
  }

  // ==================== Template Renderers ====================

  private renderSimpleCard(props: SimpleCardProps): HTMLElement {
    const card = document.createElement('div');
    card.className = 'a2ui-simple-card';

    card.innerHTML = `
      <div class="a2ui-card-header">
        ${props.icon ? `<span class="a2ui-icon">${this.getIcon(props.icon)}</span>` : ''}
        <h3 class="a2ui-card-title">${this.escapeHtml(props.title)}</h3>
      </div>
      <div class="a2ui-card-content">
        <p>${this.escapeHtml(props.content)}</p>
      </div>
    `;

    return card;
  }

  private renderTemplateGrid(props: TemplateGridProps): HTMLElement {
    const grid = document.createElement('div');
    grid.className = 'a2ui-template-grid';

    const header = document.createElement('div');
    header.className = 'a2ui-grid-header';
    header.innerHTML = `
      <h3 class="a2ui-grid-title">${this.escapeHtml(props.title)}</h3>
      ${props.showCount ? `<span class="a2ui-grid-count">${props.templates?.length || 0} items</span>` : ''}
    `;
    grid.appendChild(header);

    const items = document.createElement('div');
    items.className = 'a2ui-grid-items';

    (props.templates || []).forEach((item, idx) => {
      const card = document.createElement('div');
      card.className = 'a2ui-grid-item';
      card.style.animationDelay = `${idx * 0.1}s`;

      card.innerHTML = `
        <div class="a2ui-item-header">
          <h4 class="a2ui-item-name">${this.escapeHtml(item.name)}</h4>
          ${item.category ? `<span class="a2ui-item-category">${this.escapeHtml(item.category)}</span>` : ''}
        </div>
        <p class="a2ui-item-description">${this.escapeHtml(item.description)}</p>
      `;

      items.appendChild(card);
    });

    grid.appendChild(items);
    return grid;
  }

  private renderTimeline(props: TimelineProps): HTMLElement {
    const timeline = document.createElement('div');
    timeline.className = 'a2ui-timeline';

    const header = document.createElement('h3');
    header.className = 'a2ui-timeline-title';
    header.textContent = props.title;
    timeline.appendChild(header);

    const events = document.createElement('div');
    events.className = 'a2ui-timeline-events';

    (props.events || []).forEach((event, idx) => {
      const item = document.createElement('div');
      item.className = 'a2ui-timeline-event';
      item.style.animationDelay = `${idx * 0.15}s`;

      item.innerHTML = `
        <div class="a2ui-event-marker">
          <span class="a2ui-event-year">${this.escapeHtml(event.year)}</span>
        </div>
        <div class="a2ui-event-content">
          <h4 class="a2ui-event-title">${this.escapeHtml(event.title)}</h4>
          <p class="a2ui-event-description">${this.escapeHtml(event.description)}</p>
        </div>
      `;

      events.appendChild(item);
    });

    timeline.appendChild(events);
    return timeline;
  }

  private renderContactCard(props: ContactCardProps): HTMLElement {
    const card = document.createElement('div');
    card.className = 'a2ui-contact-card';

    const header = document.createElement('h3');
    header.className = 'a2ui-contact-title';
    header.textContent = props.title;
    card.appendChild(header);

    const contacts = document.createElement('div');
    contacts.className = 'a2ui-contact-items';

    (props.contacts || []).forEach((contact) => {
      const item = document.createElement('div');
      item.className = 'a2ui-contact-item';

      const icon = this.getContactIcon(contact.type);
      item.innerHTML = `
        <span class="a2ui-contact-icon">${icon}</span>
        <div class="a2ui-contact-info">
          <span class="a2ui-contact-value">${this.escapeHtml(contact.value)}</span>
          ${contact.description ? `<span class="a2ui-contact-desc">${this.escapeHtml(contact.description)}</span>` : ''}
        </div>
      `;

      contacts.appendChild(item);
    });

    card.appendChild(contacts);
    return card;
  }

  private renderComparisonChart(props: ComparisonChartProps): HTMLElement {
    const chart = document.createElement('div');
    chart.className = 'a2ui-comparison-chart';

    const header = document.createElement('h3');
    header.className = 'a2ui-comparison-title';
    header.textContent = props.title;
    chart.appendChild(header);

    const table = document.createElement('div');
    table.className = 'a2ui-comparison-table';

    (props.items || []).forEach((item) => {
      const column = document.createElement('div');
      column.className = 'a2ui-comparison-column';
      if (item.recommended) column.classList.add('a2ui-recommended');

      let featuresHtml = '';
      (item.features || []).forEach((f) => {
        featuresHtml += `
          <div class="a2ui-comparison-row">
            <span class="a2ui-feature-name">${this.escapeHtml(f.feature)}</span>
            <span class="a2ui-feature-value">${this.escapeHtml(f.value)}</span>
          </div>
        `;
      });

      column.innerHTML = `
        <div class="a2ui-comparison-header">
          <h4>${this.escapeHtml(item.name)}</h4>
          ${item.recommended ? '<span class="a2ui-badge">Recommended</span>' : ''}
        </div>
        <div class="a2ui-comparison-features">${featuresHtml}</div>
      `;

      table.appendChild(column);
    });

    chart.appendChild(table);
    return chart;
  }

  private renderStatsFlowLayout(props: StatsFlowLayoutProps): HTMLElement {
    const layout = document.createElement('div');
    layout.className = 'a2ui-stats-flow';

    const header = document.createElement('h3');
    header.className = 'a2ui-stats-title';
    header.textContent = props.title;
    layout.appendChild(header);

    // Top stats
    if (props.topStats?.length) {
      const topSection = document.createElement('div');
      topSection.className = 'a2ui-stats-row a2ui-stats-top';

      props.topStats.forEach((stat) => {
        const statCard = document.createElement('div');
        statCard.className = 'a2ui-stat-card';
        statCard.innerHTML = `
          <span class="a2ui-stat-value">${this.escapeHtml(stat.value)}</span>
          <span class="a2ui-stat-label">${this.escapeHtml(stat.label)}</span>
        `;
        topSection.appendChild(statCard);
      });

      layout.appendChild(topSection);
    }

    // Bottom stats
    if (props.bottomStats?.length) {
      const bottomSection = document.createElement('div');
      bottomSection.className = 'a2ui-stats-row a2ui-stats-bottom';

      props.bottomStats.forEach((stat) => {
        const statCard = document.createElement('div');
        statCard.className = 'a2ui-stat-card';
        statCard.innerHTML = `
          <span class="a2ui-stat-value">${this.escapeHtml(stat.value)}</span>
          <span class="a2ui-stat-label">${this.escapeHtml(stat.label)}</span>
        `;
        bottomSection.appendChild(statCard);
      });

      layout.appendChild(bottomSection);
    }

    return layout;
  }

  private renderTeamFlipCards(props: TeamFlipCardsProps): HTMLElement {
    const container = document.createElement('div');
    container.className = 'a2ui-team-cards';

    const header = document.createElement('h3');
    header.className = 'a2ui-team-title';
    header.textContent = props.title;
    container.appendChild(header);

    const cards = document.createElement('div');
    cards.className = 'a2ui-team-grid';

    (props.members || []).forEach((member) => {
      const card = document.createElement('div');
      card.className = 'a2ui-team-card';

      // Check for image URL (support multiple field names)
      const imageUrl = (member as any).image || (member as any).photo || (member as any).avatar || (member as any).url;
      const email = (member as any).email;
      const linkedin = (member as any).linkedin;
      const initials = member.name.substring(0, 2).toUpperCase();

      // Build front side with image or initials
      const frontAvatarHtml = imageUrl
        ? `<img src="${this.escapeHtml(imageUrl)}" alt="${this.escapeHtml(member.name)}" class="a2ui-team-avatar-img" />`
        : `<div class="a2ui-team-avatar">${initials}</div>`;

      // Build back side with bio and optional links
      let backContent = `<p class="a2ui-team-bio">${this.escapeHtml(member.bio || '')}</p>`;
      if (email || linkedin) {
        backContent += '<div class="a2ui-team-links">';
        if (email) {
          backContent += `<a href="mailto:${this.escapeHtml(email)}" class="a2ui-team-link">✉️ Email</a>`;
        }
        if (linkedin) {
          backContent += `<a href="${this.escapeHtml(linkedin)}" target="_blank" rel="noopener" class="a2ui-team-link">🔗 LinkedIn</a>`;
        }
        backContent += '</div>';
      }

      card.innerHTML = `
        <div class="a2ui-team-front">
          ${frontAvatarHtml}
          <h4 class="a2ui-team-name">${this.escapeHtml(member.name)}</h4>
          <span class="a2ui-team-role">${this.escapeHtml(member.role)}</span>
        </div>
        <div class="a2ui-team-back">
          ${backContent}
        </div>
      `;

      // Add flip interaction
      card.addEventListener('click', () => {
        card.classList.toggle('flipped');
      });

      cards.appendChild(card);
    });

    container.appendChild(cards);
    return container;
  }

  private renderServiceHoverReveal(props: ServiceHoverRevealProps): HTMLElement {
    const container = document.createElement('div');
    container.className = 'a2ui-services';

    const header = document.createElement('h3');
    header.className = 'a2ui-services-title';
    header.textContent = props.title;
    container.appendChild(header);

    const list = document.createElement('div');
    list.className = 'a2ui-services-list';

    (props.services || []).forEach((service) => {
      const item = document.createElement('div');
      item.className = 'a2ui-service-item';

      item.innerHTML = `
        <div class="a2ui-service-header">
          <h4 class="a2ui-service-name">${this.escapeHtml(service.name)}</h4>
        </div>
        <div class="a2ui-service-reveal">
          <p>${this.escapeHtml(service.description)}</p>
        </div>
      `;

      list.appendChild(item);
    });

    container.appendChild(list);
    return container;
  }

  private renderMagazineHero(props: MagazineHeroProps): HTMLElement {
    const hero = document.createElement('div');
    hero.className = 'a2ui-magazine-hero';

    hero.innerHTML = `
      <div class="a2ui-hero-header">
        <h2 class="a2ui-hero-title">${this.escapeHtml(props.title)}</h2>
        ${props.subtitle ? `<p class="a2ui-hero-subtitle">${this.escapeHtml(props.subtitle)}</p>` : ''}
      </div>
      ${props.pullQuote ? `<blockquote class="a2ui-hero-quote">"${this.escapeHtml(props.pullQuote)}"</blockquote>` : ''}
      <div class="a2ui-hero-content">
        <p>${this.escapeHtml(props.content)}</p>
      </div>
      ${props.tags?.length ? `
        <div class="a2ui-hero-tags">
          ${props.tags.map(tag => `<span class="a2ui-tag">${this.escapeHtml(tag)}</span>`).join('')}
        </div>
      ` : ''}
    `;

    return hero;
  }

  private renderFAQAccordion(props: FAQAccordionProps): HTMLElement {
    const container = document.createElement('div');
    container.className = 'a2ui-faq-accordion';

    const header = document.createElement('h3');
    header.className = 'a2ui-faq-title';
    header.textContent = props.title;
    container.appendChild(header);

    const list = document.createElement('div');
    list.className = 'a2ui-faq-list';

    (props.faqs || []).forEach((faq, idx) => {
      const item = document.createElement('div');
      item.className = 'a2ui-faq-item';
      if (idx === 0) item.classList.add('open');

      item.innerHTML = `
        <div class="a2ui-faq-question">
          <span>${this.escapeHtml(faq.question)}</span>
          <span class="a2ui-faq-icon">+</span>
        </div>
        <div class="a2ui-faq-answer">
          <p>${this.escapeHtml(faq.answer)}</p>
        </div>
      `;

      // Toggle accordion
      const questionEl = item.querySelector('.a2ui-faq-question');
      questionEl?.addEventListener('click', () => {
        item.classList.toggle('open');
      });

      list.appendChild(item);
    });

    container.appendChild(list);
    return container;
  }

  private renderImageGallery(props: ImageGalleryProps): HTMLElement {
    const gallery = document.createElement('div');
    gallery.className = 'a2ui-image-gallery';

    const header = document.createElement('h3');
    header.className = 'a2ui-gallery-title';
    header.textContent = props.title;
    gallery.appendChild(header);

    const grid = document.createElement('div');
    grid.className = 'a2ui-gallery-grid';

    (props.images || []).forEach((img) => {
      const item = document.createElement('div');
      item.className = 'a2ui-gallery-item';

      item.innerHTML = `
        <img src="${this.escapeHtml(img.url)}" alt="${this.escapeHtml(img.alt || '')}" loading="lazy" />
        ${img.caption ? `<span class="a2ui-gallery-caption">${this.escapeHtml(img.caption)}</span>` : ''}
      `;

      grid.appendChild(item);
    });

    gallery.appendChild(grid);
    return gallery;
  }

  private renderVideoGallery(props: VideoGalleryProps): HTMLElement {
    const gallery = document.createElement('div');
    gallery.className = 'a2ui-video-gallery';

    const header = document.createElement('h3');
    header.className = 'a2ui-gallery-title';
    header.textContent = props.title;
    gallery.appendChild(header);

    const grid = document.createElement('div');
    grid.className = 'a2ui-video-grid';

    (props.videos || []).forEach((video) => {
      const item = document.createElement('div');
      item.className = 'a2ui-video-item';

      // Check if YouTube URL
      const youtubeId = this.extractYouTubeId(video.url);

      if (youtubeId) {
        item.innerHTML = `
          <div class="a2ui-video-embed">
            <iframe src="https://www.youtube.com/embed/${youtubeId}"
                    frameborder="0" allowfullscreen loading="lazy"></iframe>
          </div>
          <h4 class="a2ui-video-title">${this.escapeHtml(video.title)}</h4>
        `;
      } else {
        item.innerHTML = `
          <video controls>
            <source src="${this.escapeHtml(video.url)}" type="video/mp4">
          </video>
          <h4 class="a2ui-video-title">${this.escapeHtml(video.title)}</h4>
        `;
      }

      grid.appendChild(item);
    });

    gallery.appendChild(grid);
    return gallery;
  }

  private renderFallback(props: any): HTMLElement {
    const card = document.createElement('div');
    card.className = 'a2ui-simple-card a2ui-fallback';

    card.innerHTML = `
      <div class="a2ui-card-header">
        <span class="a2ui-icon">${this.getIcon('info')}</span>
        <h3 class="a2ui-card-title">${this.escapeHtml(props.title || 'Information')}</h3>
      </div>
      <div class="a2ui-card-content">
        <p>${this.escapeHtml(JSON.stringify(props, null, 2))}</p>
      </div>
    `;

    return card;
  }

  // ==================== Helper Methods ====================

  private escapeHtml(text: string): string {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  private getIcon(name: string): string {
    const icons: Record<string, string> = {
      info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
      check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>',
      star: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>',
    };
    return icons[name] || icons.info;
  }

  private getContactIcon(type: string): string {
    const icons: Record<string, string> = {
      email: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><path d="M22 6l-10 7L2 6"/></svg>',
      phone: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/></svg>',
      address: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>',
      website: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>',
      info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
    };
    return icons[type] || icons.info;
  }

  private extractYouTubeId(url: string): string | null {
    const match = url.match(/(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/);
    return match ? match[1] : null;
  }
}

// Export singleton factory
let _rendererInstance: A2UIRenderer | null = null;

export function getA2UIRenderer(containerId: string = 'a2ui-container'): A2UIRenderer {
  if (!_rendererInstance) {
    _rendererInstance = new A2UIRenderer(containerId);
  }
  return _rendererInstance;
}
