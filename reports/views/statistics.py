from accounts.decorators import administrator_required
from django.shortcuts import render

from ..statistics import lost_statistics


@administrator_required
def lost_statistics_dashboard(request):
    return render(request, 'reports/lost_statistics.html', lost_statistics())
