from modeltranslation.translator import register, TranslationOptions

from .models import (
    SiteSettings,
    HowItWorksStep,
    DocumentRequirement,
    SuccessStory,
)


@register(SiteSettings)
class SiteSettingsTranslationOptions(TranslationOptions):
    fields = ("address", "hero_title", "hero_subtitle")


@register(HowItWorksStep)
class HowItWorksStepTranslationOptions(TranslationOptions):
    fields = ("title", "description")


@register(DocumentRequirement)
class DocumentRequirementTranslationOptions(TranslationOptions):
    fields = ("title",)


@register(SuccessStory)
class SuccessStoryTranslationOptions(TranslationOptions):
    fields = ("origin_country", "degree_level", "quote")
