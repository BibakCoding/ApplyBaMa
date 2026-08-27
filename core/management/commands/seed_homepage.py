from django.core.management.base import BaseCommand
from core.models import SiteSettings, HowItWorksStep, DocumentRequirement, SuccessStory, University, Country

# Hardcoded translations for the seed data (EN -> FA, TR, AR)
TRANSLATIONS = {
    # Site Settings
    "Unlock Your Fully Funded Future.": {
        "fa": "آینده کاملاً بورسیه شده خود را کشف کنید.",
        "tr": "Tam Burslu Geleceğinizin Kilidini Açın.",
        "ar": "اكتشف مستقبلك الممول بالكامل."
    },
    "Your trusted bridge to education abroad.": {
        "fa": "پل قابل اعتماد شما برای تحصیل در خارج از کشور.",
        "tr": "Yurtdışı eğitime giden güvenilir köprünüz.",
        "ar": "جسرك الموثوق للتعليم في الخارج."
    },

    # Journey Steps
    "Register": {"fa": "ثبت نام", "tr": "Kayıt Ol", "ar": "التسجيل"},
    "Create your free account in under a minute.": {"fa": "حساب کاربری رایگان خود را در کمتر از یک دقیقه بسازید.", "tr": "Ücretsiz hesabınızı bir dakikadan kısa sürede oluşturun.", "ar": "أنشئ حسابك المجاني في أقل من دقيقة."},

    "Browse & Choose": {"fa": "جستجو و انتخاب", "tr": "Göz At ve Seç", "ar": "تصفح واختر"},
    "Explore countries, fields and degree levels on your dashboard.": {"fa": "کشورها، رشته‌ها و مقاطع تحصیلی را در داشبورد خود بررسی کنید.", "tr": "Kontrol panelinizde ülkeleri, alanları ve derece seviyelerini keşfedin.", "ar": "استكشف البلدان والتخصصات ومستويات الشهادات من خلال لوحة التحكم الخاصة بك."},

    "Apply via WhatsApp": {"fa": "درخواست از طریق واتس‌اپ", "tr": "WhatsApp ile Başvur", "ar": "التقديم عبر واتساب"},
    "Tap apply — a ready-made WhatsApp message reaches our manager.": {"fa": "روی درخواست ضربه بزنید — یک پیام آماده واتس‌اپ به مدیر ما ارسال می‌شود.", "tr": "Başvur'a dokunun — hazır bir WhatsApp mesajı yöneticimize ulaşır.", "ar": "اضغط على التقديم - تصل رسالة واتساب جاهزة إلى مديرنا."},

    "Complete Documents": {"fa": "تکمیل مدارک", "tr": "Belgeleri Tamamla", "ar": "إكمال المستندات"},
    "Upload your documents; we check and process everything for you.": {"fa": "مدارک خود را آپلود کنید؛ ما همه چیز را برای شما بررسی و پردازش می‌کنیم.", "tr": "Belgelerinizi yükleyin; sizin için her şeyi kontrol edip işliyoruz.", "ar": "قم بتحميل مستنداتك؛ نحن نتحقق ونعالج كل شيء نيابة عنك."},

    "Get Accepted": {"fa": "دریافت پذیرش", "tr": "Kabul Al", "ar": "احصل على القبول"},
    "We handle the university process until your acceptance letter arrives.": {"fa": "ما روند دانشگاه را تا زمان رسیدن نامه پذیرش شما پیگیری می‌کنیم.", "tr": "Kabul mektubunuz gelene kadar üniversite sürecini biz yönetiyoruz.", "ar": "نتولى إجراءات الجامعة حتى تصلك رسالة القبول."},

    # Documents
    "Passport": {"fa": "پاسپورت", "tr": "Pasaport", "ar": "جواز السفر"},
    "Diploma and transcripts, with official translation": {"fa": "دیپلم و ریزنمرات، همراه با ترجمه رسمی", "tr": "Diploma ve transkript, resmi tercümesiyle", "ar": "الشهادة وكشوف الدرجات، مع الترجمة الرسمية"},
    "Pre-university certificate (for the old education system)": {"fa": "گواهی پیش‌دانشگاهی (برای نظام قدیم)", "tr": "Üniversite öncesi sertifika (eski eğitim sistemi için)", "ar": "شهادة ما قبل الجامعة (للنظام التعليمي القديم)"},
    "Bachelor's degree with transcripts, with official translation": {"fa": "مدرک لیسانس و ریزنمرات، همراه با ترجمه رسمی", "tr": "Lisans derecesi ve transkript, resmi tercümesiyle", "ar": "شهادة البكالوريوس وكشوف الدرجات، مع الترجمة الرسمية"},
    "Bachelor's degree and transcripts": {"fa": "مدرک لیسانس و ریزنمرات", "tr": "Lisans derecesi ve transkript", "ar": "شهادة البكالوريوس وكشوف الدرجات"},
    "Master's degree and transcripts, with official translation": {"fa": "مدرک فوق لیسانس و ریزنمرات، همراه با ترجمه رسمی", "tr": "Yüksek lisans derecesi ve transkript, resmi tercümesiyle", "ar": "شهادة الماجستير وكشوف الدرجات، مع الترجمة الرسمية"},
    "Motivation letter": {"fa": "انگیزه‌نامه", "tr": "Niyet mektubu", "ar": "رسالة الدافع"},
    "CV": {"fa": "رزومه", "tr": "Özgeçmiş", "ar": "السيرة الذاتية"},
    "Master's thesis": {"fa": "پایان‌نامه کارشناسی ارشد", "tr": "Yüksek lisans tezi", "ar": "رسالة الماجستير"},

    # Success Stories
    "Iran": {"fa": "ایران", "tr": "İran", "ar": "إيران"},
    "Iraq": {"fa": "عراق", "tr": "Irak", "ar": "العراق"},
    "Afghanistan": {"fa": "افغانستان", "tr": "Afganistan", "ar": "أفغانستان"},
    "Master": {"fa": "کارشناسی ارشد", "tr": "Yüksek Lisans", "ar": "ماجستير"},
    "Bachelor": {"fa": "کارشناسی", "tr": "Lisans", "ar": "بكالوريوس"},
    "From my first WhatsApp message to my acceptance letter, everything took less than two months.": {
        "fa": "از اولین پیام واتس‌اپ من تا نامه پذیرشم، همه چیز کمتر از دو ماه طول کشید.",
        "tr": "İlk WhatsApp mesajımdan kabul mektubuma kadar her şey iki aydan kısa sürdü.",
        "ar": "من أول رسالة واتساب لي إلى رسالة القبول، استغرق كل شيء أقل من شهرين."
    },
    "The team prepared my documents and kept me updated on WhatsApp at every single step.": {
        "fa": "تیم مدارک من را آماده کرد و در هر مرحله از طریق واتس‌اپ من را در جریان گذاشت.",
        "tr": "Ekip belgelerimi hazırladı ve her adımda beni WhatsApp üzerinden bilgilendirdi.",
        "ar": "قام الفريق بتجهيز مستنداتي وأبقاني على اطلاع عبر واتساب في كل خطوة."
    },
    "I never thought studying in Turkey would be this smooth. Fully guided, fully honest.": {
        "fa": "هرگز فکر نمی‌کردم تحصیل در ترکیه اینقدر راحت باشد. کاملاً راهنمایی شدم و کاملاً صادقانه.",
        "tr": "Türkiye'de okumanın bu kadar sorunsuz olacağını hiç düşünmemiştim. Tamamen rehberlik edildim, tamamen dürüst.",
        "ar": "لم أكن أعتقد أن الدراسة في تركيا ستكون بهذه السلاسة. إرشاد كامل وصدق تام."
    }
}

def t(text, lang):
    """Helper to get translation, fallback to English if missing."""
    return TRANSLATIONS.get(text, {}).get(lang, text)


class Command(BaseCommand):
    help = '✨ Seeds the database with hypothetical homepage data and auto-translates it locally!'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('🌱 Seeding & Translating homepage data...'))

        # 1. Site Settings (Singleton)
        settings, _ = SiteSettings.objects.get_or_create(id=1)
        settings.whatsapp_number = "+905344615317"
        settings.email = "Matinf1060@gmail.com"
        settings.instagram_url = "https://instagram.com/applybm"
        settings.telegram_url = "https://t.me/applybm"

        settings.hero_title = "Unlock Your Fully Funded Future."
        settings.hero_subtitle = "Your trusted bridge to education abroad."

        settings.hero_title_fa = t(settings.hero_title, "fa")
        settings.hero_title_tr = t(settings.hero_title, "tr")
        settings.hero_title_ar = t(settings.hero_title, "ar")
        settings.hero_subtitle_fa = t(settings.hero_subtitle, "fa")
        settings.hero_subtitle_tr = t(settings.hero_subtitle, "tr")
        settings.hero_subtitle_ar = t(settings.hero_subtitle, "ar")

        settings.save()
        self.stdout.write(self.style.SUCCESS('   ✅ Site Settings translated and updated.'))

        # 2. Create a dummy country for Success Stories
        country, _ = Country.objects.get_or_create(name="Turkey", defaults={"language": "Turkish", "nationality": "Turkish"})

        # 3. Universities
        unis = [
            "Aydın University", "Bahçeşehir University", "Medipol University", "Yeni Yüzyıl University",
            "Biruni University", "Kent University", "Üsküdar University", "Nişantaşı University"
        ]
        for name in unis:
            try:
                uni = University.objects.get(name__iexact=name)
                uni.show_on_homepage = True
                uni.save(update_fields=['show_on_homepage'])
            except University.DoesNotExist:
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
        HowItWorksStep.objects.all().delete()
        for i, (icon, title, desc) in enumerate(steps_data, start=1):
            HowItWorksStep.objects.create(
                order=i, icon_class=icon, title=title, description=desc, is_active=True,
                title_fa=t(title, "fa"), title_tr=t(title, "tr"), title_ar=t(title, "ar"),
                description_fa=t(desc, "fa"), description_tr=t(desc, "tr"), description_ar=t(desc, "ar")
            )
        self.stdout.write(self.style.SUCCESS('   ✅ Journey Steps translated and created.'))

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
            DocumentRequirement.objects.create(
                level=level, title=title,
                title_fa=t(title, "fa"), title_tr=t(title, "tr"), title_ar=t(title, "ar")
            )
        self.stdout.write(self.style.SUCCESS('   ✅ Document Requirements translated and created.'))

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
            SuccessStory.objects.create(
                name=name, origin_country=origin, destination_university=dest, degree_level=level, quote=quote, instagram_video_url=url, is_published=True,
                origin_country_fa=t(origin, "fa"), origin_country_tr=t(origin, "tr"), origin_country_ar=t(origin, "ar"),
                degree_level_fa=t(level, "fa"), degree_level_tr=t(level, "tr"), degree_level_ar=t(level, "ar"),
                quote_fa=t(quote, "fa"), quote_tr=t(quote, "tr"), quote_ar=t(quote, "ar")
            )
        self.stdout.write(self.style.SUCCESS('   ✅ Success Stories translated and created.'))

        self.stdout.write(self.style.SUCCESS('\n🎉 Successfully seeded and translated all homepage data instantly! Refresh your browser.'))
