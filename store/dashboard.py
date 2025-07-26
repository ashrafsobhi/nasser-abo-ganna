from jet.dashboard.dashboard import Dashboard
from jet.dashboard.modules import AppList, RecentActions
from django.utils.translation import gettext_lazy as _

class CustomIndexDashboard(Dashboard):
    """
    A simplified dashboard for debugging.
    It should display the app list and recent actions in two columns.
    """
    columns = 2

    def init_with_context(self, context):
        self.children.append(AppList(
            _('Applications'),
            column=0,
            order=0
        ))
        self.children.append(RecentActions(
            _('Recent Actions'),
            column=1,
            order=0
        )) 