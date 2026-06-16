document.addEventListener("DOMContentLoaded", function () {
    const toggleButton = document.getElementById("toggleFilterButton");
    const filterContainer = document.getElementById("filterContainer");
    const filterForm = document.querySelector('.filter-form');
    const loader = document.getElementById('loader');
    const paginationLinks = document.querySelectorAll(".pagination-link");

    // Tombol Tampilkan/Sembunyikan Filter
    if (toggleButton && filterContainer) {
        toggleButton.addEventListener("click", function () {
            filterContainer.classList.toggle("hidden");
            toggleButton.textContent = filterContainer.classList.contains("hidden")
                ? "Tampilkan Filter"
                : "Sembunyikan Filter";
        });
    }

    // Loader muncul saat form disubmit
    if (filterForm && loader) {
        filterForm.addEventListener('submit', function (event) {
        event.preventDefault(); // menghentikan submit default agar tidak dobel
            loader.classList.remove('hidden');
            loader.classList.add('show');
    
    setTimeout(() => {
        filterForm.submit(); // submit form setelah 1 detik
            }, 1000); // 1 detik = 1000ms
        });
    }

    paginationLinks.forEach(link => {
        link.addEventListener("click", function (e) {
            // Cegah default redirect agar bisa kasih jeda
            e.preventDefault();

            const url = this.getAttribute("href");

            // Tunda munculnya loader selama 1.5 detik
            setTimeout(() => {
                loader.classList.remove("hidden");
                loader.classList.add("show");
            }, 1500);

            // Redirect ke halaman tujuan setelah 1.5 detik juga
            setTimeout(() => {
                window.location.href = url;
            }, 1500);
        });
    });
});
