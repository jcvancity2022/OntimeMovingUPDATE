// Demo-only widget proving the template reskins live via CSS variables.
// Safe to delete this file and the .theme-switcher block in index.html for production use.
document.querySelectorAll('.theme-swatch').forEach((swatch) => {
  swatch.addEventListener('click', () => {
    document.documentElement.setAttribute('data-theme', swatch.dataset.theme);
    document.querySelectorAll('.theme-swatch').forEach((s) => s.classList.remove('active'));
    swatch.classList.add('active');
  });
});

const navToggle = document.querySelector('.nav-toggle');
const navLinks = document.querySelector('.nav-links');
if (navToggle && navLinks) {
  navToggle.addEventListener('click', () => {
    navLinks.style.display = navLinks.style.display === 'flex' ? 'none' : 'flex';
  });
}
