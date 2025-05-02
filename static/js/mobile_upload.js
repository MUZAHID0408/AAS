// static/js/mobile-upload.js
function openCamera() {
    const fileInput = document.getElementById('fileInput');
    fileInput.setAttribute('capture', 'environment');
    fileInput.click();
  }
  
  function openGallery() {
    const fileInput = document.getElementById('fileInput');
    fileInput.removeAttribute('capture');
    fileInput.click();
  }
  
  // Handle file selection
  document.getElementById('fileInput').addEventListener('change', function(e) {
    const previewContainer = document.getElementById('imagePreview');
    previewContainer.innerHTML = ''; // Clear previous previews
    
    if (this.files && this.files.length > 0) {
      Array.from(this.files).forEach(file => {
        if (!file.type.match('image.*')) return;
        
        const reader = new FileReader();
        reader.onload = function(e) {
          const preview = document.createElement('div');
          preview.className = 'image-preview';
          preview.innerHTML = `
            <img src="${e.target.result}" alt="Preview">
            <span>${file.name}</span>
          `;
          previewContainer.appendChild(preview);
        }
        reader.readAsDataURL(file);
      });
    }
  });