document.querySelectorAll('.side-panel__themes--single_card').forEach(card => {
  card.addEventListener('click', () => {
    const theme = card.getAttribute('data-theme');
    document.body.classList.remove('light-theme', 'dark-theme', 'colorblind-theme');
    document.body.classList.add(`${theme}-theme`);
    localStorage.setItem('theme', theme);
  });
});

const savedTheme = localStorage.getItem('theme') || 'light';
document.body.classList.add(`${savedTheme}-theme`);
