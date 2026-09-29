var isDarkMode = localStorage.getItem('darkMode') === 'true';
function toggleDarkMode() {
  isDarkMode = !isDarkMode;
  localStorage.setItem('darkMode', isDarkMode);
  var html = document.documentElement;
  var btn = document.querySelector('.dark-toggle');
  if (isDarkMode) { html.classList.add('dark'); btn.textContent = '\uD83C\uDF19'; }
  else { html.classList.remove('dark'); btn.textContent = '\u2600\uFE0F'; }
}
if (isDarkMode) {
  document.documentElement.classList.add('dark');
  document.addEventListener('DOMContentLoaded', function(){
    var b=document.querySelector('.dark-toggle'); if(b) b.textContent='\uD83C\uDF19';
  });
  var b=document.querySelector('.dark-toggle'); if(b) b.textContent='\uD83C\uDF19';
}
