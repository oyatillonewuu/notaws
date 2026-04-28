"""Re-exports subapp models so Django's migration system sees them under
the ec2 app. Subapps are Python packages, not registered Django apps."""
from ec2.subapps.image_builds.models import ImageBuild
from ec2.subapps.images.models import Image
from ec2.subapps.instances.models import Instance

__all__ = ["ImageBuild", "Image", "Instance"]
