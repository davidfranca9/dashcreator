const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
if (!reducedMotion.matches) document.documentElement.classList.add('motion');
if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); }
  }), { threshold: .12 });
  document.querySelectorAll('.reveal').forEach(element => observer.observe(element));
}

const dialog = document.querySelector('#event-video');
if (dialog) {
const video = dialog.querySelector('video');
const videoStatus = dialog.querySelector('.video-status');
let trigger;
document.querySelectorAll('[data-video]').forEach(button => button.addEventListener('click', async () => {
  trigger = button;
  videoStatus.hidden = true;
  dialog.showModal();
  document.body.style.overflow = 'hidden';
  try { await video.play(); }
  catch { if (dialog.open) { videoStatus.textContent = 'Toque no controle de reprodução para assistir.'; videoStatus.hidden = false; } }
}));
dialog.querySelector('.modal-close').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', event => {
  if (event.target === dialog) {
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  }
});
dialog.addEventListener('close', () => {
  video.pause();
  document.body.style.overflow = '';
  trigger?.focus({ preventScroll: true });
});
video.addEventListener('error', () => {
  videoStatus.textContent = 'Não foi possível carregar o vídeo. Tente abrir novamente.';
  videoStatus.hidden = false;
});
}

const inlineVideo = document.querySelector('#original-video');
if (inlineVideo) {
  const stage = inlineVideo.closest('[data-inline-stage]');
  const playButton = stage.querySelector('[data-inline-play]');
  const backButton = stage.querySelector('[data-inline-close]');
  const overlay = stage.querySelector('.immersive-content');
  if (overlay) inlineVideo.controls = false;
  playButton.addEventListener('click', async () => {
    inlineVideo.controls = true;
    try { await inlineVideo.play(); }
    catch { inlineVideo.controls = true; }
  });
  inlineVideo.addEventListener('play', () => {
    stage.classList.add('is-playing');
    if (backButton) backButton.hidden = false;
    if (overlay) overlay.inert = true;
  });
  function returnToInvitation() {
    inlineVideo.pause();
    stage.classList.remove('is-playing');
    if (backButton) backButton.hidden = true;
    if (overlay) { overlay.inert = false; inlineVideo.controls = false; }
  }
  inlineVideo.addEventListener('ended', returnToInvitation);
  backButton?.addEventListener('click', () => {
    returnToInvitation();
    playButton.focus({ preventScroll: true });
  });
}

const form = document.querySelector('#waitlist');
const LEAD_ENDPOINT = 'https://app.thecreatorsclub.com.br/api/creator-day-lead/';
const phone = form.elements.phone;
const error = form.querySelector('.form-error');
phone.addEventListener('input', () => {
  const digits = phone.value.replace(/\D/g, '').slice(0, 11);
  const split = digits.length === 11 ? 7 : 6;
  phone.value = digits.length <= 2 ? digits : digits.length <= 6 ? `(${digits.slice(0, 2)}) ${digits.slice(2)}` : `(${digits.slice(0, 2)}) ${digits.slice(2, split)}-${digits.slice(split)}`;
});
form.addEventListener('input', event => event.target.removeAttribute('aria-invalid'));
form.addEventListener('submit', async event => {
  event.preventDefault();
  error.hidden = true;
  form.querySelectorAll('[aria-invalid]').forEach(field => field.removeAttribute('aria-invalid'));
  const name = form.elements.fullName;
  const email = form.elements.email;
  let invalid;
  let message;
  if (!name.value.trim()) { invalid = name; message = 'Preencha seu nome para continuar.'; }
  else if (!email.value.trim() || !email.validity.valid || !/^\S+@\S+\.\S+$/.test(email.value.trim())) { invalid = email; message = 'Confira seu e-mail para continuar.'; }
  else if (phone.value.replace(/\D/g, '').length < 10) { invalid = phone; message = 'Informe seu WhatsApp com DDD.'; }
  if (invalid) {
    error.textContent = message;
    error.hidden = false;
    invalid.setAttribute('aria-invalid', 'true');
    invalid.focus();
    return;
  }
  const submit = form.querySelector('[type="submit"]');
  submit.disabled = true;
  submit.textContent = 'Salvando seus dados…';
  // Salva o contato no CRM (coluna Interesse) e depois abre o grupo no WhatsApp.
  // Se a rede falhar ou demorar, segue para o grupo do mesmo jeito.
  const envio = fetch(LEAD_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'text/plain;charset=utf-8' },
    body: JSON.stringify({
      name: name.value.trim(),
      email: email.value.trim(),
      whatsapp: phone.value.trim(),
      page: document.body.classList.contains('editorial') ? 'editorial' : 'imersivo',
      site: form.elements.empresa ? form.elements.empresa.value : '',
    }),
    keepalive: true,
  }).catch(() => null);
  await Promise.race([envio, new Promise(resolve => setTimeout(resolve, 4000))]);
  submit.textContent = 'Abrindo o WhatsApp…';
  window.location.assign('https://chat.whatsapp.com/ByTHxx6230SDaf5Ky5UoLA');
});
addEventListener('pageshow', () => {
  const submit = form.querySelector('[type="submit"]');
  submit.disabled = false;
  submit.innerHTML = 'Quero prioridade no evento <span class="arrow" aria-hidden="true">→</span>';
});

// Cascata ao rolar: cada filho de [data-stagger] entra um pouco depois do
// anterior. So liga com movimento permitido e IntersectionObserver disponivel;
// fora disso os elementos ficam visiveis e parados.
if (document.documentElement.classList.contains('motion') && 'IntersectionObserver' in window) {
  const grupos = document.querySelectorAll('[data-stagger]');
  grupos.forEach(grupo => [...grupo.children].forEach((filho, i) => filho.style.setProperty('--i', i)));
  document.documentElement.classList.add('stagger-ready');
  const cascata = new IntersectionObserver(entradas => entradas.forEach(entrada => {
    if (entrada.isIntersecting) { entrada.target.classList.add('is-visible'); cascata.unobserve(entrada.target); }
  }), { threshold: .15 });
  grupos.forEach(grupo => cascata.observe(grupo));
}

// Fotos do encontro: cada moldura [data-slides] troca de foto a cada 6 s.
// Com movimento reduzido fica parada na primeira; com a aba escondida nao troca.
if (document.documentElement.classList.contains('motion')) {
  document.querySelectorAll('[data-slides]').forEach(moldura => {
    const fotos = [...moldura.querySelectorAll('img')];
    if (fotos.length < 2) return;
    let atual = 0;
    setInterval(() => {
      if (document.hidden) return;
      fotos[atual].classList.remove('is-active');
      atual = (atual + 1) % fotos.length;
      fotos[atual].classList.add('is-active');
    }, 6000);
  });
}
