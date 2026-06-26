from django.urls import path
from frontend import views

app_name = 'frontend'

urlpatterns = [
    path('', views.home, name='home'),

    path('about/', views.about, name='about'),

    path('services/', views.services, name='services'),

    path('contact/', views.contact, name='contact'),

]