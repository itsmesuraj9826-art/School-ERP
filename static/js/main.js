// Martyrs' Memorial Martyrs Memorial +2 — Main JS

document.addEventListener('DOMContentLoaded', function () {

    // ── Sidebar Toggle (Mobile) ──────────────────────────
    const menuToggle = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('mainContent');

    if (menuToggle && sidebar) {
        menuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
        mainContent && mainContent.addEventListener('click', () => {
            sidebar.classList.remove('open');
        });
    }

    // ── Dark Mode Toggle ─────────────────────────────────
    const darkToggle = document.getElementById('darkModeToggle');
    const html = document.documentElement;
    const savedTheme = localStorage.getItem('erp-theme') || 'light';
    html.setAttribute('data-theme', savedTheme);
    updateDarkIcon(savedTheme);

    darkToggle && darkToggle.addEventListener('click', () => {
        const current = html.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-theme', next);
        localStorage.setItem('erp-theme', next);
        updateDarkIcon(next);
    });

    function updateDarkIcon(theme) {
        const icon = darkToggle && darkToggle.querySelector('i');
        if (icon) {
            icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
    }

    // ── Animated Counters ────────────────────────────────
    const counters = document.querySelectorAll('.counter');
    if (counters.length) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animateCounter(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.2 });

        counters.forEach(c => observer.observe(c));
    }

    function animateCounter(el) {
        const target = parseInt(el.getAttribute('data-target')) || 0;
        const duration = 1800;
        const step = target / (duration / 16);
        let current = 0;
        const timer = setInterval(() => {
            current += step;
            if (current >= target) {
                el.textContent = target.toLocaleString();
                clearInterval(timer);
            } else {
                el.textContent = Math.floor(current).toLocaleString();
            }
        }, 16);
    }

    // ── Auto-dismiss alerts ──────────────────────────────
    const alerts = document.querySelectorAll('.alert-custom');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 5000);
    });

    // ── DataTables Init ──────────────────────────────────
    if (typeof $.fn.DataTable !== 'undefined') {
        const tables = ['#studentsTable', '#teachersTable'];
        tables.forEach(id => {
            if ($(id).length && !$.fn.DataTable.isDataTable(id)) {
                $(id).DataTable({
                    responsive: true,
                    pageLength: 15,
                    language: {
                        search: '<i class="fas fa-search"></i>',
                        lengthMenu: 'Show _MENU_',
                        info: '_START_ – _END_ of _TOTAL_',
                        paginate: {
                            previous: '<i class="fas fa-chevron-left"></i>',
                            next: '<i class="fas fa-chevron-right"></i>'
                        }
                    },
                    dom: '<"d-flex justify-content-between align-items-center mb-3"lf>t<"d-flex justify-content-between mt-3"ip>'
                });
            }
        });
    }

    // ── Staggered entrance for cards ─────────────────────
    const cards = document.querySelectorAll('.stat-card, .info-card, .class-card, .assignment-card');
    cards.forEach((card, i) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(16px)';
        setTimeout(() => {
            card.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, i * 60);
    });

    // ── Score bar animation ───────────────────────────────
    const scoreBars = document.querySelectorAll('.score-bar');
    const barObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.transition = 'width 1s cubic-bezier(0.4,0,0.2,1)';
            }
        });
    });
    scoreBars.forEach(b => barObserver.observe(b));

    // ── Tooltips ─────────────────────────────────────────
    const tooltipEls = document.querySelectorAll('[title]');
    tooltipEls.forEach(el => {
        new bootstrap.Tooltip(el, { placement: 'top', trigger: 'hover' });
    });

    // ── Active nav link highlight ─────────────────────────
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });

});
