document.addEventListener('DOMContentLoaded', function() {
    // Initialize Select2 on country and city dropdowns
    const $countrySelect = $('#id_country');
    const $citySelect = $('#id_city');

    if ($countrySelect.length) {
        // Initialize Select2 for country
        $countrySelect.select2({
            placeholder: 'Select a country',
            allowClear: true,
            width: '100%',
            theme: 'default'
        });

        // Initialize Select2 for city
        if ($citySelect.length) {
            $citySelect.select2({
                placeholder: 'Select a city',
                allowClear: true,
                width: '100%'
            });
        }

        // 🔥 CRITICAL: When country changes, immediately update cities
        $countrySelect.on('change', function() {
            const countryId = $(this).val();

            // Clear city dropdown
            $citySelect.empty().append('<option value="">Select a city</option>');

            if (countryId) {
                // Show loading state
                $citySelect.prop('disabled', true);

                // Fetch cities for selected country via AJAX
                fetch(`/dashboard/get-cities/?country_id=${countryId}`, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': window.CSRF_TOKEN || document.querySelector('[name=csrfmiddlewaretoken]').value
                    }
                })
                .then(response => response.json())
                .then(data => {
                    // Populate cities
                    data.cities.forEach(city => {
                        $citySelect.append(new Option(city.name, city.id, false, false));
                    });

                    // Re-enable and refresh Select2
                    $citySelect.prop('disabled', false);
                    $citySelect.trigger('change');
                })
                .catch(error => {
                    console.error('Error loading cities:', error);
                    $citySelect.prop('disabled', false);
                });
            } else {
                // No country selected, disable city dropdown
                $citySelect.prop('disabled', true);
                $citySelect.trigger('change');
            }
        });
    }
});
