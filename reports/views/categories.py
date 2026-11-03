"""Gestion del catalogo de categorias por parte de un administrador.

RF14 Manage Categories
"""

from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from accounts.decorators import administrator_required

from ..forms import CategoryForm
from ..models import Category


@administrator_required
def category_list(request):
    categories = Category.objects.all().order_by("name")

    return render(
        request,
        "reports/category_list.html",
        {"categories": categories},
    )


@administrator_required
def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Category created successfully."))
            return redirect("administration_category_list")
    else:
        form = CategoryForm()

    return render(
        request,
        "reports/category_form.html",
        {
            "form": form,
            "title": _("Create Category"),
            "submit_label": _("Create Category"),
        },
    )


@administrator_required
def category_edit(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, _("Category updated successfully."))
            return redirect("administration_category_list")
    else:
        form = CategoryForm(instance=category)

    return render(
        request,
        "reports/category_form.html",
        {
            "form": form,
            "category": category,
            "title": _("Edit Category"),
            "submit_label": _("Save Changes"),
        },
    )


@administrator_required
def category_delete(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    if request.method == "POST":
        try:
            category.delete()
        except ProtectedError:
            messages.error(
                request,
                _("This category cannot be deleted because it is currently used by one or more reports."),
            )
            return redirect("administration_category_list")

        messages.success(request, _("Category deleted successfully."))
        return redirect("administration_category_list")

    return render(
        request,
        "reports/category_confirm_delete.html",
        {"category": category},
    )
