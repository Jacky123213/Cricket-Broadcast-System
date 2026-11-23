/* Consistent, accessible guidance for every image picker, including dynamic rows. */
(() => {
  'use strict';
  const kinds={teamLogoUpload:'logo',upload1:'logo',upload2:'logo',playerPhotoUpload:'portrait',
    comingImage:'coming',foxComingImage:'coming',sponsorImage:'sponsor',foxSponsorImage:'sponsor',
    broadcastLogoFile:'logo',brandingUpload:'logo'};
  const sizes={logo:'512 × 512 px (transparent PNG recommended)',portrait:'600 × 800 px',
    coming:'640 × 360 px',sponsor:'1920 × 135 px (wide banner; fills the row)'};
  let counter=0;
  function enhance(input){if(input.dataset.imageHelp==='ready'||!input.accept.includes('image/'))return;
    const kind=input.dataset.uploadKind||kinds[input.id]||'logo',hint=document.createElement('small');
    hint.id='imageUploadHint'+(++counter);hint.className='image-upload-hint';hint.textContent='PNG/JPEG · Max 1 MB · Suggested '+(sizes[kind]||sizes.logo)+'.';
    input.dataset.imageHelp='ready';input.setAttribute('aria-describedby',[input.getAttribute('aria-describedby'),hint.id].filter(Boolean).join(' '));input.after(hint);
  }
  function scan(node){if(node.nodeType!==1)return;if(Element.prototype.matches.call(node,'input[type=file]'))enhance(node);for(const input of node.querySelectorAll('input[type=file]'))enhance(input);}
  function start(){scan(document.body);new MutationObserver(rows=>{for(const row of rows)for(const node of row.addedNodes)scan(node);}).observe(document.body,{childList:true,subtree:true});}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
