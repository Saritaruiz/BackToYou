"""Borra del disco las imagenes que dejan de estar asociadas a un reporte.

Django nunca elimina el archivo subido: al borrar un reporte o al reemplazar
su imagen, el archivo anterior queda para siempre en MEDIA_ROOT. Estas dos
senales cierran esa fuga.
"""

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import ItemReport


def _borrar_archivo(imagen):
    if imagen and imagen.name:
        imagen.storage.delete(imagen.name)


@receiver(post_delete, sender=ItemReport)
def borrar_imagen_al_eliminar_reporte(sender, instance, **kwargs):
    _borrar_archivo(instance.image)


@receiver(pre_save, sender=ItemReport)
def borrar_imagen_reemplazada(sender, instance, **kwargs):
    if not instance.pk:
        return

    anterior = sender.objects.filter(pk=instance.pk).only("image").first()
    if anterior is None:
        return

    if anterior.image and anterior.image.name != instance.image.name:
        _borrar_archivo(anterior.image)
