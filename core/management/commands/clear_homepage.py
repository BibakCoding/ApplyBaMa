from django.core.management.base import BaseCommand
from core.models import SiteSettings, HowItWorksStep, DocumentRequirement, SuccessStory, University

class Command(BaseCommand):
    help = '🧹 Clears all hypothetical homepage data'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('🧹 Clearing homepage data...'))

        # DO NOT delete universities! They might be real scraped data.
        # Just hide them from the homepage.
        University.objects.all().update(show_on_homepage=False)
        self.stdout.write(self.style.SUCCESS('   ✅ Universities hidden from homepage.'))

        # Safe to delete these because they are purely for the homepage layout
        HowItWorksStep.objects.all().delete()
        DocumentRequirement.objects.all().delete()
        SuccessStory.objects.all().delete()

        # Reset SiteSettings
        SiteSettings.objects.all().delete()

        self.stdout.write(self.style.SUCCESS('\n✅ Successfully cleared homepage data!'))
