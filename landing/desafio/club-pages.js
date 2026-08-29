const mobileButton=document.querySelector('[data-mobile-menu]');
const mobilePanel=document.querySelector('[data-mobile-panel]');
if(mobileButton&&mobilePanel)mobileButton.addEventListener('click',()=>{const open=mobilePanel.classList.toggle('is-open');mobileButton.setAttribute('aria-expanded',String(open))});

document.querySelectorAll('[data-like]').forEach(button=>button.addEventListener('click',()=>{
  const liked=button.classList.toggle('is-liked');
  const count=button.closest('.post').querySelector('[data-like-count]');
  const value=Number(count.dataset.value||0)+(liked?1:-1);count.dataset.value=String(value);count.textContent=`${value} curtida${value===1?'':'s'}`;
}));
document.querySelectorAll('[data-comment-toggle]').forEach(button=>button.addEventListener('click',()=>button.closest('.post').querySelector('.comment-box').classList.toggle('is-open')));

const composer=document.querySelector('[data-composer]');
const publish=document.querySelector('[data-publish]');
if(composer&&publish){composer.addEventListener('input',()=>publish.disabled=!composer.value.trim());publish.addEventListener('click',()=>{if(!composer.value.trim())return;composer.value='';publish.disabled=true;showToast('Publicação adicionada ao protótipo.')})}

const copy=document.querySelector('[data-copy]');
if(copy)copy.addEventListener('click',async()=>{const code=document.querySelector('[data-code]').textContent.trim();try{await navigator.clipboard.writeText(code)}catch{}showToast('Código copiado!')});
function showToast(message){const toast=document.querySelector('[data-toast]');if(!toast)return;toast.textContent=message;toast.classList.add('is-visible');setTimeout(()=>toast.classList.remove('is-visible'),2200)}
