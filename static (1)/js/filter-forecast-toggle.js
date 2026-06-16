document.addEventListener("DOMContentLoaded", function () {
    const toggleButton = document.getElementById("toggleFilterBtn");
    const filterContainer = document.getElementById("filterForecastContainer");
    const filterForm = document.querySelector('.filter-forecast-form');
    const loaderForecasting = document.getElementById('loaderForecasting');
    const paginationLinks = document.querySelectorAll(".forecasting-konsumsi");

    if (toggleButton && filterContainer) {
        toggleButton.addEventListener("click", function () {
            filterContainer.classList.toggle("hidden-forecast");
            toggleButton.textContent = filterContainer.classList.contains("hidden-forecast")
                ? "Tampilkan Filter"
                : "Sembunyikan Filter";
        });
    }

    if (filterForm && loaderForecasting) {
        filterForm.addEventListener('submit', function (event) {
            event.preventDefault();
                loaderForecasting.classList.remove('hidden');
                loaderForecasting.classList.add('show');

            setTimeout(() => {
                filterForm.submit();
            }, 1000);
        });
    }

    paginationLinks.forEach(link => {
        link.addEventListener("click", function (e) {
            e.preventDefault();
            const url = this.getAttribute("href");

            loader.classList.remove("hidden");
            loader.classList.add("show");

            setTimeout(() => {
                window.location.href = url;
            }, 1500);
        });
    });
});
