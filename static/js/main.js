// Gestion du mode sombre/clair
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const icon = document.getElementById('theme-icon');
    if (icon) {
        icon.textContent = theme === 'light' ? '🌙' : '☀️';
        icon.title = theme === 'light' ? 'Mode sombre' : 'Mode clair';
    }
}

// Gestion de la langue
function initLanguage() {
    const savedLang = localStorage.getItem('language') || 'fr';
    setLanguage(savedLang);
}

function setLanguage(lang) {
    localStorage.setItem('language', lang);
    updateLanguageUI(lang);
    translatePage(lang);
}

function updateLanguageUI(lang) {
    const frBtn = document.getElementById('lang-fr');
    const enBtn = document.getElementById('lang-en');
    
    if (frBtn && enBtn) {
        if (lang === 'fr') {
            frBtn.classList.add('active');
            enBtn.classList.remove('active');
        } else {
            enBtn.classList.add('active');
            frBtn.classList.remove('active');
        }
    }
}

function translatePage(lang) {
    // Traductions
    const translations = {
        fr: {
            // Navigation
            'nav_home': 'Accueil',
            'nav_dashboard': 'Tableau de bord',
            'nav_new_article': 'Nouvel article',
            'nav_my_articles': 'Mes articles',
            'nav_pending_reviews': 'Relectures en attente',
            'nav_admin_panel': 'Panel admin',
            'nav_profile': 'Profil',
            'nav_logout': 'Déconnexion',
            'nav_login': 'Connexion',
            'nav_register': 'Inscription',
            'nav_welcome': 'Bienvenue',
            
            // Général
            'welcome': 'Bienvenue sur Journal Platform',
            'login': 'Se connecter',
            'register': 'Créer un compte',
            'logout': 'Déconnexion',
            'profile': 'Profil',
            'dashboard': 'Tableau de bord',
            'save': 'Enregistrer',
            'cancel': 'Annuler',
            'delete': 'Supprimer',
            'edit': 'Modifier',
            'view': 'Voir',
            
            // Footer
            'footer_platform': 'Plateforme de gestion de journal académique avec système d\'évaluation par les pairs.',
            'footer_quick_links': 'Liens rapides',
            'footer_roles': 'Rôles',
            'footer_contact': 'Contact',
            'footer_copyright': 'Tous droits réservés.',
            
            // Rôles
            'role_author': 'Auteur',
            'role_reviewer': 'Relecteur',
            'role_editor': 'Éditeur',
            
            // Articles
            'articles': 'Articles',
            'create_article': 'Créer un article',
            'title': 'Titre',
            'abstract': 'Résumé',
            'content': 'Contenu',
            'keywords': 'Mots-clés',
            'status': 'Statut',
            'submitted': 'Soumis',
            'published': 'Publié',
            'rejected': 'Rejeté',
            'pending': 'En attente',
            
            // Reviews
            'reviews': 'Relectures',
            'submit_review': 'Soumettre une relecture',
            'recommendation': 'Recommandation',
            'comments': 'Commentaires',
            'score': 'Note',
            
            // Users
            'users': 'Utilisateurs',
            'username': 'Nom d\'utilisateur',
            'email': 'Email',
            'password': 'Mot de passe',
            
            // Actions
            'actions': 'Actions',
            'confirm_delete': 'Êtes-vous sûr de vouloir supprimer ?',
        },
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
            
            'welcome': 'Welcome to Journal Platform',
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
    
    // Traduire tous les éléments avec l'attribut data-translate
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
    
    // Traduire le titre de la page
    const titleKey = document.querySelector('title')?.getAttribute('data-translate');
    if (titleKey && translations[lang][titleKey]) {
        document.title = translations[lang][titleKey];
    }
}

// Initialisation au chargement de la page
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initLanguage();
});
