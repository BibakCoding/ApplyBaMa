from django.db import models


class ConnectSID(models.Model):
    """
    Stores the current 'connect.sid' from info.studyfans.com,
    plus a timestamp of when it was fetched.
    """
    sid = models.CharField(max_length=500, help_text="Current connect.sid cookie value")
    fetched_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sid[:30]}… (fetched {self.fetched_at})"

    class Meta:
        verbose_name = "Stored ConnectSID"
        verbose_name_plural = "Stored ConnectSIDs"
