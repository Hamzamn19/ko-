(function () {
    const AURORA_LIGHT_PROPS = {
        mouseForce: 14,
        cursorSize: 80,
        colors: ['#5227FF','#FF9FFC','#B497CF'],
        autoSpeed: 0.5,
        autoIntensity: 2.2
    };

    const AURORA_DARK_PROPS = {
        mouseForce: 14,
        cursorSize: 80,
        colors: ['#3a1f99','#994d99','#6b5080'],
        autoSpeed: 0.4,
        autoIntensity: 2.0
    };

    function applyThemeFromStorage() {
        const stored = localStorage.getItem('theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const dark = stored ? stored === 'dark' : prefersDark;
        document.documentElement.classList.toggle('dark', dark);
        syncThemeIcon();
    }

    function syncThemeIcon() {
        const icon = document.getElementById('theme-icon');
        if (!icon) return;
        icon.textContent = document.documentElement.classList.contains('dark') ? 'dark_mode' : 'light_mode';
    }

    function toggleTheme() {
        const isDark = document.documentElement.classList.toggle('dark');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        syncThemeIcon();
    }

    function initNavPanel() {
        const nav = document.getElementById('app-nav');
        const toggle = document.getElementById('nav-toggle');
        const close = document.getElementById('nav-close');
        if (!nav || !toggle) return;

        const setOpen = (open) => {
            nav.classList.toggle('is-open', open);
        };

        toggle.addEventListener('click', () => setOpen(!nav.classList.contains('is-open')));
        if (close) close.addEventListener('click', () => setOpen(false));
        document.addEventListener('keydown', (ev) => {
            if (ev.key === 'Escape') setOpen(false);
        });
        document.addEventListener('click', (ev) => {
            if (window.innerWidth > 980) return;
            const target = ev.target;
            if (!(target instanceof Node)) return;
            if (!nav.contains(target) && !toggle.contains(target)) setOpen(false);
        });
    }

    function initActiveNav() {
        const path = window.location.pathname;
        document.querySelectorAll('.nav-link').forEach((link) => {
            const href = link.getAttribute('href');
            link.classList.toggle('is-active', href === path);
        });
    }

    let auroraController = null;
    let auroraHost = null;

    async function initAuroraBackground() {
        const ambientLayer = document.querySelector('.ambient-layer');
        if (!ambientLayer) return;
        auroraHost = ambientLayer.querySelector('.aurora-layer');
        if (!auroraHost) return;
        if (!window.Aurora || typeof window.Aurora.mount !== 'function') {
            console.warn('Aurora module is unavailable. Include /static/Aurora.js before dashboard-ui.js.');
            return;
        }

        // Respect saved preference
        if (localStorage.getItem('bgfx') === 'off') {
            ambientLayer.style.display = 'none';
            return;
        }

        const getAuroraThemeProps = () => (
            document.documentElement.classList.contains('dark') ? AURORA_DARK_PROPS : AURORA_LIGHT_PROPS
        );

        try {
            auroraController = await window.Aurora.mount(auroraHost, getAuroraThemeProps());

            const observer = new MutationObserver(() => {
                auroraController?.update(getAuroraThemeProps());
            });
            observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });

            window.addEventListener('beforeunload', () => {
                observer.disconnect();
                auroraController?.destroy();
            });
        } catch (err) {
            console.error('Aurora background failed to initialize:', err);
        }
    }

    function syncFxButton() {
        const status = document.getElementById('fx-status');
        if (!status) return;
        const isOff = localStorage.getItem('bgfx') === 'off';
        status.textContent = isOff ? 'OFF' : 'ON';
        status.style.background = isOff ? 'rgba(239,68,68,0.12)' : 'rgba(34,197,94,0.14)';
        status.style.borderColor = isOff ? 'rgba(239,68,68,0.36)' : 'rgba(34,197,94,0.36)';
    }

    async function toggleFx() {
        const ambientLayer = document.querySelector('.ambient-layer');
        if (!ambientLayer) return;
        const isCurrentlyOn = localStorage.getItem('bgfx') !== 'off';

        if (isCurrentlyOn) {
            // Turn off
            localStorage.setItem('bgfx', 'off');
            if (auroraController) { auroraController.destroy(); auroraController = null; }
            ambientLayer.style.display = 'none';
        } else {
            // Turn on
            localStorage.setItem('bgfx', 'on');
            ambientLayer.style.display = '';
            if (!auroraController && auroraHost && window.Aurora) {
                const getProps = () => document.documentElement.classList.contains('dark') ? AURORA_DARK_PROPS : AURORA_LIGHT_PROPS;
                try {
                    auroraController = await window.Aurora.mount(auroraHost, getProps());
                } catch (e) { console.error('Failed to re-mount FX:', e); }
            }
        }
        syncFxButton();
    }

    function initFxToggle() {
        syncFxButton();
        const btn = document.getElementById('fx-toggle');
        if (btn) btn.addEventListener('click', toggleFx);
    }

    function init() {
        applyThemeFromStorage();
        initNavPanel();
        initActiveNav();
        initAuroraBackground();
        initFxToggle();

        window.toggleTheme = toggleTheme;
        window.toggleFx = toggleFx;
    }

    document.addEventListener('DOMContentLoaded', init);
})();

