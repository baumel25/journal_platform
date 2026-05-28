// =============================================
// Instructor: Journal of Computer Science and Applications - Main JavaScript
// =============================================

// Smooth page transitions
document.addEventListener('DOMContentLoaded', function() {
    // Fade in animation for main content
    const main = document.querySelector('.main-content');
    if (main) {
        main.style.opacity = '0';
        requestAnimationFrame(() => {
            main.style.transition = 'opacity 0.3s ease';
            main.style.opacity = '1';
        });
    }

    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Add hover effect to table rows
    document.querySelectorAll('.table tbody tr').forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.transition = 'background 0.2s ease';
        });
    });

    // Animate stat cards on scroll
    const statCards = document.querySelectorAll('.stat-card');
    if (statCards.length > 0) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry, index) => {
                if (entry.isIntersecting) {
                    setTimeout(() => {
                        entry.target.style.opacity = '1';
                        entry.target.style.transform = 'translateY(0)';
                    }, index * 100);
                }
            });
        }, { threshold: 0.1 });

        statCards.forEach(card => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            card.style.transition = 'all 0.4s ease';
            observer.observe(card);
        });
    }

    // Animate article cards on scroll
    const articleCards = document.querySelectorAll('.article-card');
    if (articleCards.length > 0) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry, index) => {
                if (entry.isIntersecting) {
                    setTimeout(() => {
                        entry.target.style.opacity = '1';
                        entry.target.style.transform = 'translateY(0)';
                    }, index * 100);
                }
            });
        }, { threshold: 0.1 });

        articleCards.forEach(card => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            card.style.transition = 'all 0.4s ease';
            observer.observe(card);
        });
    }

    // Animate feature cards on home page
    const featureCards = document.querySelectorAll('.feature-card');
    if (featureCards.length > 0) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry, index) => {
                if (entry.isIntersecting) {
                    setTimeout(() => {
                        entry.target.style.opacity = '1';
                        entry.target.style.transform = 'translateY(0)';
                    }, index * 150);
                }
            });
        }, { threshold: 0.1 });

        featureCards.forEach(card => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(30px)';
            card.style.transition = 'all 0.5s ease';
            observer.observe(card);
        });
    }
});

// Smooth scroll for anchor links
document.addEventListener('click', function(e) {
    const target = e.target.closest('a[href^="#"]');
    if (target) {
        const id = target.getAttribute('href');
        if (id !== '#') {
            const element = document.querySelector(id);
            if (element) {
                e.preventDefault();
                element.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    }
});

// Confirmation dialog for delete actions
function confirmAction(message) {
    return confirm(message || 'Are you sure you want to proceed?');
}

// Copy to clipboard utility
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        const toast = document.createElement('div');
        toast.className = 'position-fixed bottom-0 end-0 p-3';
        toast.style.zIndex = '9999';
        toast.innerHTML = `
            <div class="alert alert-success alert-dismissible fade show shadow rounded-4 mb-0" role="alert">
                <i class="bi bi-check-circle me-2"></i>Copied to clipboard!
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 2000);
    }).catch(() => {
        // Fallback for older browsers
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
    });
}

// ─── Translations ───────────────────────────────────────────────────────────
const translations = {
    en: {
            'nav_home': 'Home',
            'nav_dashboard': 'Dashboard',
            'nav_new_article': 'New article',
            'nav_my_articles': 'My articles',
            'nav_pending_reviews': 'Pending reviews',
            'nav_admin_panel': 'Admin panel',
            'nav_profile': 'Profile',
            'nav_logout': 'Logout',
            'nav_login': 'Login',
            'nav_register': 'Register',
            'nav_welcome': 'Welcome',
            
            'welcome': 'Welcome to Instructor: Journal of Computer Science and Applications',
            'login': 'Login',
            'register': 'Register',
            'logout': 'Logout',
            'profile': 'Profile',
            'dashboard': 'Dashboard',
            'save': 'Save',
            'cancel': 'Cancel',
            'delete': 'Delete',
            'edit': 'Edit',
            'view': 'View',
            
            'footer_platform': 'Academic journal management platform with peer review system.',
            'footer_quick_links': 'Quick links',
            'footer_roles': 'Roles',
            'footer_contact': 'Contact',
            'footer_copyright': 'All rights reserved.',
            
            'role_author': 'Author',
            'role_reviewer': 'Reviewer',
            'role_editor': 'Editor',
            
            'articles': 'Articles',
            'create_article': 'Create article',
            'title': 'Title',
            'abstract': 'Abstract',
            'content': 'Content',
            'keywords': 'Keywords',
            'status': 'Status',
            'submitted': 'Submitted',
            'published': 'Published',
            'rejected': 'Rejected',
            'pending': 'Pending',
            
            'reviews': 'Reviews',
            'submit_review': 'Submit review',
            'recommendation': 'Recommendation',
            'comments': 'Comments',
            'score': 'Score',
            
            'users': 'Users',
            'username': 'Username',
            'email': 'Email',
            'password': 'Password',
            
            'actions': 'Actions',
            'confirm_delete': 'Are you sure you want to delete?',
        }
    };
    
    // ─── Language & Theme Initialization ────────────────────────────────────
    function initLanguage(lang) {
    lang = lang || localStorage.getItem('language') || 'en';
    
    // Translate all elements with data-translate attribute
    document.querySelectorAll('[data-translate]').forEach(element => {
        const key = element.getAttribute('data-translate');
        if (translations[lang] && translations[lang][key]) {
            if (element.tagName === 'INPUT' && element.placeholder) {
                element.placeholder = translations[lang][key];
            } else {
                element.textContent = translations[lang][key];
            }
        }
    });
    
    // Translate the page title
    const titleKey = document.querySelector('title')?.getAttribute('data-translate');
    if (titleKey && translations[lang][titleKey]) {
        document.title = translations[lang][titleKey];
    }
}

// ─── Theme Toggle ───────────────────────────────────────────────────────────
function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-theme');
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initLanguage();
});
