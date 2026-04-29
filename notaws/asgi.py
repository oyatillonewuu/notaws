<<<<<<< HEAD
"""
ASGI config for notaws project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

=======
>>>>>>> feat/isolate-ec2-in-agent-code
import os

from django.core.asgi import get_asgi_application

<<<<<<< HEAD
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'notaws.settings')
=======
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "notaws.settings")
>>>>>>> feat/isolate-ec2-in-agent-code

application = get_asgi_application()
