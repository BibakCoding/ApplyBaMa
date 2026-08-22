from django.core.management.base import BaseCommand
from core.models import SiteSettings, HowItWorksStep, DocumentRequirement, SuccessStory, University, Country

class Command(BaseCommand):
    help = '✨ Seeds the database with hypothetical homepage data'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('🌱 Seeding homepage data...'))

        # 1. Site Settings (Singleton)
        settings, _ = SiteSettings.objects.get_or_create(id=1)
        settings.whatsapp_number = "+905344615317"
        settings.email = "Matinf1060@gmail.com"
        settings.instagram_url = "https://instagram.com/applybm"
        settings.telegram_url = "https://t.me/applybm"
        settings.hero_title = "Unlock Your Fully Funded Future."
        settings.hero_subtitle = "Your trusted bridge to education abroad."
        settings.save()
        self.stdout.write(self.style.SUCCESS('   ✅ Site Settings updated.'))

        # 2. Create a dummy country for Success Stories
        country, _ = Country.objects.get_or_create(name="Turkey", defaults={"language": "Turkish", "nationality": "Turkish"})

        # 3. Universities (Handle Case-Insensitive uniqueness safely!)
        unis = [
            "Aydın University", "Bahçeşehir University", "Medipol University", "Yeni Yüzyıl University",
            "Biruni University", "Kent University", "Üsküdar University", "Nişantaşı University"
        ]
        for name in unis:
            try:
                # Try to find it case-insensitively
                uni = University.objects.get(name__iexact=name)
                uni.show_on_homepage = True
                uni.save(update_fields=['show_on_homepage'])
            except University.DoesNotExist:
                # If it doesn't exist at all, create it
                uni = University.objects.create(name=name, country=country, show_on_homepage=True)
        self.stdout.write(self.style.SUCCESS('   ✅ Universities updated/created.'))

        # 4. How It Works Steps
        steps_data = [
            ("fas fa-user-plus", "Register", "Create your free account in under a minute."),
            ("fas fa-search", "Browse & Choose", "Explore countries, fields and degree levels on your dashboard."),
            ("fab fa-whatsapp", "Apply via WhatsApp", "Tap apply — a ready-made WhatsApp message reaches our manager."),
            ("fas fa-file-alt", "Complete Documents", "Upload your documents; we check and process everything for you."),
            ("fas fa-plane-departure", "Get Accepted", "We handle the university process until your acceptance letter arrives."),
        ]
        HowItWorksStep.objects.all().delete() # Clear existing to avoid duplicates
        for i, (icon, title, desc) in enumerate(steps_data, start=1):
            HowItWorksStep.objects.create(order=i, icon_class=icon, title=title, description=desc, is_active=True)
        self.stdout.write(self.style.SUCCESS('   ✅ Journey Steps created.'))

        # 5. Document Requirements
        DocumentRequirement.objects.all().delete()
        docs_data = [
            ('associate_bachelor', "Passport"),
            ('associate_bachelor', "Diploma and transcripts, with official translation"),
            ('associate_bachelor', "Pre-university certificate (for the old education system)"),
            ('master', "Passport"),
            ('master', "Bachelor's degree with transcripts, with official translation"),
            ('phd', "Passport"),
            ('phd', "Bachelor's degree and transcripts"),
            ('phd', "Master's degree and transcripts, with official translation"),
            ('phd', "Motivation letter"),
            ('phd', "CV"),
            ('phd', "Master's thesis"),
        ]
        for level, title in docs_data:
            DocumentRequirement.objects.create(level=level, title=title)
        self.stdout.write(self.style.SUCCESS('   ✅ Document Requirements created.'))

        # 6. Success Stories
        SuccessStory.objects.all().delete()
        uni = University.objects.filter(name__iexact="Bahçeşehir University").first()
        if not uni:
             uni = University.objects.create(name="Bahçeşehir University", country=country, show_on_homepage=True)

        stories_data = [
            ("Sara M.", "Iran", uni, "Master", "From my first WhatsApp message to my acceptance letter, everything took less than two months.", "https://instagram.com"),
            ("Ahmed K.", "Iraq", uni, "Bachelor", "The team prepared my documents and kept me updated on WhatsApp at every single step.", "https://instagram.com"),
            ("Fatima R.", "Afghanistan", uni, "Master", "I never thought studying in Turkey would be this smooth. Fully guided, fully honest.", "https://instagram.com"),
        ]
        for name, origin, dest, level, quote, url in stories_data:
            SuccessStory.objects.create(name=name, origin_country=origin, destination_university=dest, degree_level=level, quote=quote, instagram_video_url=url, is_published=True)
        self.stdout.write(self.style.SUCCESS('   ✅ Success Stories created.'))

        self.stdout.write(self.style.SUCCESS('\n🎉 Successfully seeded homepage data! Refresh your browser.'))
