"""
A2UI Template Library for Nester AI Voice Assistant

Pre-defined templates for automatic selection based on query content.
Each template type corresponds to a specific visual layout in the frontend.

Template Types:
- template-grid: Grid of cards for lists (projects, products, services)
- timeline: Chronological events display
- contact-card: Contact information card
- comparison-chart: Side-by-side comparison
- stats-flow-layout: Dashboard with KPIs and metrics
- team-flip-cards: Team member profiles
- service-hover-reveal: Service listings with hover details
- magazine-hero: Long-form content display
- faq-accordion: Q&A accordion
- image-gallery / video-gallery: Media galleries
"""

from typing import Dict, Any, List
import json
from loguru import logger


# Template library with v1 nested format (simpler for voice assistant)
TEMPLATE_LIBRARY: Dict[str, Dict[str, Any]] = {
    "template-grid": {
        "version": "1.0",
        "root": {
            "type": "template-grid",
            "props": {
                "title": "",
                "templates": [{"name": "", "description": "", "category": ""}],
                "columns": 3,
                "showSearch": True,
                "showCount": True
            }
        }
    },

    "timeline": {
        "version": "1.0",
        "root": {
            "type": "timeline",
            "props": {
                "title": "",
                "events": [{"year": "", "title": "", "description": ""}],
                "orientation": "vertical"
            }
        }
    },

    "comparison-chart": {
        "version": "1.0",
        "root": {
            "type": "comparison-chart",
            "props": {
                "title": "",
                "items": [{"name": "", "features": [{"feature": "", "value": ""}]}]
            }
        }
    },

    "contact-card": {
        "version": "1.0",
        "root": {
            "type": "contact-card",
            "props": {
                "title": "",
                "contacts": [{"type": "", "value": "", "description": ""}]
            }
        }
    },

    "image-gallery": {
        "version": "1.0",
        "root": {
            "type": "image-gallery",
            "props": {
                "title": "",
                "images": [{"url": "", "caption": "", "alt": ""}],
                "layout": "grid"
            }
        }
    },

    "video-gallery": {
        "version": "1.0",
        "root": {
            "type": "video-gallery",
            "props": {
                "title": "",
                "videos": [{"url": "", "title": "", "description": ""}],
                "layout": "grid"
            }
        }
    },

    "team-flip-cards": {
        "version": "1.0",
        "root": {
            "type": "team-flip-cards",
            "props": {
                "title": "",
                "members": [{"name": "", "role": "", "bio": ""}]
            }
        }
    },

    "service-hover-reveal": {
        "version": "1.0",
        "root": {
            "type": "service-hover-reveal",
            "props": {
                "title": "",
                "services": [{"name": "", "description": ""}]
            }
        }
    },

    "stats-flow-layout": {
        "version": "1.0",
        "root": {
            "type": "stats-flow-layout",
            "props": {
                "title": "",
                "topStats": [{"label": "", "value": ""}],
                "radialProgress": {"label": "", "completion_rate": ""},
                "performanceMetrics": [{"label": "", "value": ""}],
                "bottomStats": [{"label": "", "value": ""}]
            }
        }
    },

    "stats-chart": {
        "version": "1.0",
        "root": {
            "type": "stats-chart",
            "props": {
                "title": "",
                "stats": [{"label": "", "value": ""}],
                "charts": [{"type": "bar", "title": "", "data": [{"name": "", "value": ""}]}]
            }
        }
    },

    "magazine-hero": {
        "version": "1.0",
        "root": {
            "type": "magazine-hero",
            "props": {
                "title": "",
                "subtitle": "",
                "content": "",
                "metadata": {"author": "", "date": ""},
                "tags": [],
                "pullQuote": ""
            }
        }
    },

    "faq-accordion": {
        "version": "1.0",
        "root": {
            "type": "faq-accordion",
            "props": {
                "title": "",
                "faqs": [{"question": "", "answer": ""}],
                "variant": "searchable"
            }
        }
    },

    "blog-magazine": {
        "version": "1.0",
        "root": {
            "type": "blog-magazine",
            "props": {
                "title": "",
                "posts": [{"title": "", "excerpt": "", "category": ""}],
                "variant": "magazine"
            }
        }
    },

    "sales-dashboard": {
        "version": "1.0",
        "root": {
            "type": "sales-dashboard",
            "props": {
                "title": "",
                "subtitle": "",
                "kpiCards": [{"title": "", "value": "", "icon": "DollarSign", "variant": "primary"}],
                "charts": [{"type": "bar", "title": "", "data": [{"name": "", "value": ""}], "xAxisKey": "name", "yAxisKey": "value"}]
            }
        }
    },

    # Simple text card for basic responses
    "simple-card": {
        "version": "1.0",
        "root": {
            "type": "simple-card",
            "props": {
                "title": "",
                "content": "",
                "icon": ""
            }
        }
    }
}


def get_template_from_library(template_type: str) -> Dict[str, Any]:
    """
    Get template structure by type.

    Args:
        template_type: Template type name

    Returns:
        Template structure dictionary. Falls back to simple-card if not found.
    """
    logger.debug(f"📋 get_template_from_library called for: '{template_type}'")
    
    if template_type in TEMPLATE_LIBRARY:
        logger.debug(f"   ✅ Template found: {template_type}")
        import copy
        return copy.deepcopy(TEMPLATE_LIBRARY[template_type])
    else:
        logger.warning(f"   ⚠️ Template '{template_type}' not found, using 'simple-card' fallback")
        import copy
        return copy.deepcopy(TEMPLATE_LIBRARY["simple-card"])


def get_template_catalog() -> str:
    """
    Build a compact template catalog string for LLM template selection.
    """
    catalog = [
        {"type": "service-hover-reveal", "when": "services, offerings, capabilities"},
        {"type": "contact-card", "when": "contact info, phone, email, address"},
        {"type": "template-grid", "when": "list of items: projects, products, features"},
        {"type": "timeline", "when": "chronological events, history, milestones"},
        {"type": "comparison-chart", "when": "comparing multiple items side by side"},
        {"type": "team-flip-cards", "when": "team members, people profiles"},
        {"type": "faq-accordion", "when": "questions and answers, FAQ"},
        {"type": "stats-flow-layout", "when": "numeric data, KPIs, metrics, statistics"},
        {"type": "magazine-hero", "when": "descriptive text, about us, overview"},
        {"type": "image-gallery", "when": "image URLs, photos, screenshots"},
        {"type": "video-gallery", "when": "video URLs, YouTube links"},
        {"type": "simple-card", "when": "simple text response, default fallback"},
    ]
    return json.dumps(catalog, separators=(',', ':'))


def list_available_templates() -> Dict[str, Any]:
    """
    List all available templates with metadata for semantic selector.
    """
    templates_metadata = {
        "count": len(TEMPLATE_LIBRARY),
        "templates": [
            {
                "type": "template-grid",
                "name": "Template Grid",
                "description": "Grid layout for multiple items like projects, products, services, features",
                "use_cases": ["project listings", "product showcase", "service offerings", "feature lists"],
                "trigger_keywords": ["projects", "list", "show me", "products", "services", "features", "items"]
            },
            {
                "type": "timeline",
                "name": "Timeline",
                "description": "Chronological event timeline for history, milestones, roadmap",
                "use_cases": ["company history", "project timeline", "milestones", "roadmap"],
                "trigger_keywords": ["timeline", "history", "when", "founded", "milestones", "chronological"]
            },
            {
                "type": "comparison-chart",
                "name": "Comparison Chart",
                "description": "Side-by-side comparison for products, plans, options",
                "use_cases": ["product comparison", "plan comparison", "feature comparison"],
                "trigger_keywords": ["compare", "comparison", "versus", "vs", "difference", "better"]
            },
            {
                "type": "contact-card",
                "name": "Contact Card",
                "description": "Contact information card with email, phone, address",
                "use_cases": ["contact information", "get in touch", "reach us"],
                "trigger_keywords": ["contact", "phone", "reach", "address", "email", "location"]
            },
            {
                "type": "team-flip-cards",
                "name": "Team Flip Cards",
                "description": "Team member profiles with flip animation",
                "use_cases": ["team members", "staff profiles", "leadership"],
                "trigger_keywords": ["team", "members", "staff", "people", "employees", "who"]
            },
            {
                "type": "service-hover-reveal",
                "name": "Service Hover Reveal",
                "description": "Service cards with hover-reveal details",
                "use_cases": ["services offered", "what we do", "capabilities"],
                "trigger_keywords": ["services", "offerings", "what we do", "capabilities"]
            },
            {
                "type": "stats-flow-layout",
                "name": "Stats Flow Layout",
                "description": "Statistics dashboard with KPIs and metrics",
                "use_cases": ["analytics dashboard", "performance metrics", "KPI tracking"],
                "trigger_keywords": ["analytics", "metrics", "KPI", "statistics", "numbers", "data"]
            },
            {
                "type": "magazine-hero",
                "name": "Magazine Hero",
                "description": "Magazine-style content for articles and descriptions",
                "use_cases": ["article display", "blog post", "detailed explanation"],
                "trigger_keywords": ["article", "about", "tell me", "describe", "explain", "what is"]
            },
            {
                "type": "faq-accordion",
                "name": "FAQ Accordion",
                "description": "Expandable FAQ for questions and answers",
                "use_cases": ["frequently asked questions", "Q&A section", "help"],
                "trigger_keywords": ["faq", "questions", "q&a", "help", "how to"]
            },
            {
                "type": "image-gallery",
                "name": "Image Gallery",
                "description": "Interactive image gallery",
                "use_cases": ["display images", "photo gallery", "screenshots"],
                "trigger_keywords": ["image", "photo", "picture", "logo", "screenshot"]
            },
            {
                "type": "video-gallery",
                "name": "Video Gallery",
                "description": "Video gallery for tutorials and demos",
                "use_cases": ["video collection", "tutorial videos", "demo videos"],
                "trigger_keywords": ["video", "watch", "youtube", "tutorial", "demo"]
            },
            {
                "type": "simple-card",
                "name": "Simple Card",
                "description": "Simple text card for basic responses",
                "use_cases": ["simple answer", "basic response", "default"],
                "trigger_keywords": []
            }
        ]
    }
    return templates_metadata
