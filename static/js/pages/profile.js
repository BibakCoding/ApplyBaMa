document.addEventListener('DOMContentLoaded', function() {
    // Initialize Select2 on country and city dropdowns
    const $countrySelect = $('.select2-country');
    const $citySelect = $('.select2-city');

    if ($countrySelect.length) {
        $countrySelect.select2({
            placeholder: 'Select a country',
            allowClear: true,
            width: '100%',
            theme: 'default'
        });

        // When country changes, load cities
        $countrySelect.on('change', function() {
            const countryId = $(this).val();

            // Clear city dropdown
            $citySelect.empty().append('<option value="">Select a city</option>');

            if (countryId) {
                // Fetch cities for selected country
                fetch(`/dashboard/get-cities/?country_id=${countryId}`, {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                })
                .then(response => response.json())
                .then(data => {
                    data.cities.forEach(city => {
                        $citySelect.append(`<option value="${city.id}">${city.name}</option>`);
                    });
                    $citySelect.trigger('change'); // Refresh Select2
                })
                .catch(error => console.error('Error loading cities:', error));
            }

            // Re-initialize Select2 for city
            $citySelect.select2({
                placeholder: 'Select a city',
                allowClear: true,
                width: '100%'
            });
        });
    }

    // Initialize city Select2
    if ($citySelect.length) {
        $citySelect.select2({
            placeholder: 'Select a city',
            allowClear: true,
            width: '100%'
        });
    }
});
