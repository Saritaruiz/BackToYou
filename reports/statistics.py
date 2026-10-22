"""RF25: read-only statistics for currently stored Lost submissions."""
from datetime import datetime, timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import ItemReport


def lost_statistics():
    lost = ItemReport.objects.filter(report_type=ItemReport.ReportType.LOST)
    summary = lost.aggregate(
        total=Count('pk'),
        active=Count('pk', filter=Q(status=ItemReport.Status.ACTIVE)),
        recovered=Count('pk', filter=Q(status=ItemReport.Status.RECOVERED)),
        pending=Count('pk', filter=Q(status=ItemReport.Status.PENDING_REVIEW)),
        rejected=Count('pk', filter=Q(status=ItemReport.Status.REJECTED)),
    )
    approved = summary['active'] + summary['recovered']
    summary['recovery_rate'] = round(100 * summary['recovered'] / approved, 1) if approved else None
    categories = list(lost.values('category_id', 'category__name').annotate(total=Count('pk'))
                      .order_by('-total', 'category__name', 'category_id'))
    maximum = max((row['total'] for row in categories), default=1)
    for row in categories:
        row['percent'] = round(100 * row['total'] / maximum, 2)

    tz = timezone.get_current_timezone()
    today = timezone.localdate()
    current = today.year * 12 + today.month - 1

    def month_boundary(index):
        year, month = divmod(index, 12)
        return timezone.make_aware(datetime(year, month + 1, 1), tz)

    start, end = month_boundary(current - 11), month_boundary(current + 1)
    counts = {
        (row['month'].year, row['month'].month): row['total']
        for row in lost.filter(created_at__gte=start, created_at__lt=end)
        .annotate(month=TruncMonth('created_at', tzinfo=tz))
        .values('month').annotate(total=Count('pk')).order_by('month')
    }
    months = []
    for index in range(current - 11, current + 1):
        month = month_boundary(index)
        months.append({'month': month, 'total': counts.get((month.year, month.month), 0)})
    maximum = max((row['total'] for row in months), default=0) or 1
    for row in months:
        row['percent'] = round(100 * row['total'] / maximum, 2)
    return {'summary': summary, 'categories': categories, 'months': months,
            'statistics_timezone': str(tz)}


def community_numbers():
    """Inicio: numeros reales que muestran que BackToYou funciona.

    La tasa de recuperacion es la misma de RF25: Recovered / (Active +
    Recovered) entre los reportes Lost.
    """
    now = timezone.now()
    last_day = now - timedelta(days=1)
    active = Q(status=ItemReport.Status.ACTIVE)
    recovered = Q(status=ItemReport.Status.RECOVERED)
    lost = Q(report_type=ItemReport.ReportType.LOST)
    # Un reporte se publica cuando lo aprueban; sin fecha de moderacion
    # cuenta su fecha de creacion, como en el feed de RF24.
    published_last_day = Q(moderated_at__gte=last_day) | Q(moderated_at__isnull=True, created_at__gte=last_day)

    numbers = ItemReport.objects.aggregate(
        active=Count('pk', filter=active),
        recovered=Count('pk', filter=recovered),
        returned_this_week=Count('pk', filter=recovered & Q(recovered_at__gte=now - timedelta(days=7))),
        new_last_day=Count('pk', filter=active & published_last_day),
        lost_active=Count('pk', filter=lost & active),
        lost_recovered=Count('pk', filter=lost & recovered),
    )
    approved = numbers.pop('lost_active') + numbers['lost_recovered']
    numbers['recovery_rate'] = round(100 * numbers.pop('lost_recovered') / approved, 1) if approved else None
    return numbers
