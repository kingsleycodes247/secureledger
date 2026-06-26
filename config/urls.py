from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),

    path('', include('frontend.urls')),

    path('control/', include('adminpanel.urls')),

    # Authentication (register, login, logout, email-verify, password reset)
    path('accounts/', include('accounts.urls')),

    # Authenticated dashboard & all inner pages
    path('dashboard/', include('dashboard.urls')),

    # Investment API helpers (plan list, subscribe, etc.)
    path('invest/', include('investments.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
