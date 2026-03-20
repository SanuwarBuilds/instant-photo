const fs = require('fs');
const html = fs.readFileSync('index.html', 'utf8');

const ids = [
  'dropZone', 'imageInput', 'photoList', 'addMoreWrapper', 'addMoreBtn',
  'generateBtn', 'downloadBtn', 'pdfPreview', 'loading', 'toggleAdvanced',
  'advancedOptions', 'cropperModal', 'cropModalImage', 'confirmCropBtn',
  'cancelCropBtn', 'notification', 'notification-message', 'feedbackBtn',
  'feedbackModal', 'closeModal', 'feedbackForm', 'bgColorLabel',
  'customColorBtn', 'customColorInput'
];

ids.forEach(id => {
  if (!html.includes(`id="${id}"`) && !html.includes(`id='${id}'`)) {
    console.log(`MISSING ID: ${id}`);
  }
});
