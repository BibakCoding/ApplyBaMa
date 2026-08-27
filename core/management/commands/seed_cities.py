import geonamescache
from django.core.management.base import BaseCommand
from core.models import Country, City

class Command(BaseCommand):
    help = '🌍 Seeds major cities for all countries using geonamescache'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('🌍 Fetching global geographic data...'))

        gc = geonamescache.GeonamesCache()
        countries_data = gc.get_countries()
        cities_data = gc.get_cities()

        # Map our database countries by lowercase name for fast lookup
        db_countries = {c.name.lower(): c for c in Country.objects.all()}

        if not db_countries:
            self.stdout.write(self.style.ERROR('❌ No countries found in DB! Run `python manage.py seed_countries` first.'))
            return

        cities_to_create = []
        skipped_count = 0

        self.stdout.write(self.style.WARNING('🏙️ Filtering and preparing cities (this takes a few seconds)...'))

        for city_id, city_info in cities_data.items():
            country_code = city_info['countrycode']
            country_info = countries_data.get(country_code)

            if not country_info:
                continue

            country_name = country_info['name']
            db_country = db_countries.get(country_name.lower())

            # If the country doesn't exist in our DB, skip the city
            if not db_country:
                skipped_count += 1
                continue

            # 🔥 CRITICAL FILTER: Only keep major cities (Population > 15,000)
            # This prevents the DB from being flooded with tiny villages.
            population = city_info.get('population', 0)
            if population < 15000:
                skipped_count += 1
                continue

            city_name = city_info['name']

            # Prepare the City object
            cities_to_create.append(
                City(
                    external_id=city_id,
                    country=db_country,
                    name=city_name
                )
            )

        # Bulk create for maximum speed.
        # ignore_conflicts=True prevents errors if the city already exists (due to unique_together constraint)
        if cities_to_create:
            self.stdout.write(self.style.WARNING(f'💾 Inserting {len(cities_to_create)} cities into database...'))
            City.objects.bulk_create(cities_to_create, ignore_conflicts=True)
            self.stdout.write(self.style.SUCCESS(f'✅ Successfully seeded {len(cities_to_create)} major cities!'))
        else:
            self.stdout.write(self.style.WARNING('⚠️ No new cities to add.'))

        self.stdout.write(self.style.SUCCESS(f'📊 Total cities in database: {City.objects.count()}'))
        self.stdout.write(self.style.WARNING(f'🗑️ Skipped {skipped_count} tiny villages/unmatched countries.'))
