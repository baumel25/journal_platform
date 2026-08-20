"""Sitemaps so search engines can discover the journal's pages and articles."""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from articles.models import Article


class ArticleSitemap(Sitemap):
    """Published articles only (publicly readable pages)."""
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return Article.objects.filter(status="published").order_by("-published_date")

    def location(self, obj):
        return reverse("article_detail", args=[obj.pk])

    def lastmod(self, obj):
        return obj.published_date or obj.updated_at


class StaticSitemap(Sitemap):
    """Key static pages of the site."""
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return ["home", "journal_about"]

    def location(self, item):
        return reverse(item)
