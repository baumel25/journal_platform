from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse, Http404
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from articles import views as article_views
from journal_project.sitemaps import ArticleSitemap, StaticSitemap

sitemaps = {
    'articles': ArticleSitemap,
    'static': StaticSitemap,
}


def robots_txt(request):
    """Simple robots.txt pointing search engines at the sitemap."""
    lines = [
        "User-agent: *",
        "Disallow:",
        "Sitemap: https://i-jcsa.com/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def google_verification_file(request):
    """Serve the Google Search Console ownership verification file."""
    return HttpResponse(
        "google-site-verification: google0c3c4fd399199736.html",
        content_type="text/html",
    )


urlpatterns = [
    path('admin/', admin.site.urls),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('google0c3c4fd399199736.html', google_verification_file, name='google_verification_file'),
    # The site opens on the journal hub page (SCIRP-style journal landing).
    path('', article_views.journal_hub, name='home'),
    path('accounts/', include('accounts.urls')),
    path('articles/', include('articles.urls')),
]

# Serve media files in all environments
def protected_media(request, path):
    """Serve media files, but never expose raw uploaded article documents.

    Files under ``article_files/`` (the uploaded manuscripts / published PDFs)
    are only accessible through the permission-checked download views, so paid
    access cannot be bypassed by guessing the file URL.
    """
    if path.startswith('article_files/'):
        raise Http404('Article files are protected.')
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns += [re_path(r'^media/(?P<path>.*)$', protected_media)]

# Serve static files in all environments
urlpatterns += [re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT})]
