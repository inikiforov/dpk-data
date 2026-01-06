"""
URL routes for dpk-blog.
Includes: index, portfolio, blog, settings.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Public pages
    path('', views.index, name='index'),
    path('open/', views.portfolio_public, name='portfolio_public'),
    
    # Portfolio management (login required)
    path('lab/portfolio-v3/', views.lab_portfolio_v3, name='lab_portfolio_v3'),
    path('lab/settings/', views.lab_settings, name='lab_settings'),
    path('lab/settings/update-prices/', views.lab_update_prices, name='lab_update_prices'),
    
    # Blog
    path('blog/', views.blog_index, name='blog_index'),
    path('blog/drafts/', views.blog_drafts, name='blog_drafts'),
    path('blog/new/', views.blog_editor, name='blog_editor_new'),
    path('blog/edit/<slug:slug>/', views.blog_editor, name='blog_editor_edit'),
    path('blog/api/upload-image/', views.blog_upload_image, name='blog_upload_image'),
    path('blog/api/seo-report/<slug:slug>/', views.blog_seo_report, name='blog_seo_report'),
    path('blog/<slug:slug>/', views.post_detail, name='post_detail'),
]
