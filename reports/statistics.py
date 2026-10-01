"""RF25: read-only statistics for currently stored Lost submissions."""
from datetime import datetime

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
