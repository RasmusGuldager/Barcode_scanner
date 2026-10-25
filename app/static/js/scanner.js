// Live camera scanner.
//
// Starts the camera in every element with a data-scanner attribute. Each scan is
// written to the "code" field of the form named by data-scanner, and the form is
// submitted. htmx handles the submit on the rent/return pages, so the camera keeps
// running between scans.
//
// Decoding is done by zxing-wasm (zxing-cpp compiled to WebAssembly). We tried
// html5-qrcode first, but it failed to read about 1 in 20 of our labels.

(function () {
  // Formats per scanner kind: QR labels, or the 1D barcode on the AAU card.
  const FORMATS = { qr: ["QRCode"], card: ["AllLinear"] };
  // Time between two decode attempts.
  const SCAN_INTERVAL_MS = 150;
  // The camera sees the same label many times per second; ignore repeats.
  const REPEAT_DELAY_MS = 3000;

  const wasmUrl = document.currentScript.dataset.wasm;
  ZXingWASM.prepareZXingModule({
    overrides: {
      locateFile: (path, prefix) => (path.endsWith(".wasm") ? wasmUrl : prefix + path),
    },
  });

  function showStatus(element, text) {
    const status = element.parentElement.querySelector(".scanner-status");
    status.hidden = false;
    status.textContent = text;
  }

  async function openCamera() {
    return navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: "environment",
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
    });
  }

  async function start(element) {
    const form = document.getElementById(element.dataset.scanner);
    const input = form.querySelector('[name="code"]');
    const formats = FORMATS[element.dataset.kind];

    if (!navigator.mediaDevices) {
      showStatus(element, "The camera only works over HTTPS. Type the code below instead.");
      return;
    }
    let stream;
    try {
      stream = await openCamera();
    } catch (error) {
      showStatus(element, "The camera could not be started. Allow camera access, or type the code below.");
      return;
    }

    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true; // iOS: don't go fullscreen
    video.srcObject = stream;
    element.appendChild(video);
    await video.play();

    // Stop the camera when leaving the page, so the phone's camera light goes off.
    window.addEventListener("pagehide", () => stream.getTracks().forEach((t) => t.stop()));

    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d", { willReadFrequently: true });
    let lastText = "";
    let lastTime = 0;

    function handle(text) {
      const now = Date.now();
      if (text === lastText && now - lastTime < REPEAT_DELAY_MS) {
        return;
      }
      lastText = text;
      lastTime = now;
      if (navigator.vibrate) {
        navigator.vibrate(60);
      }
      input.value = text;
      form.requestSubmit();
    }

    async function scanFrame() {
      if (!document.hidden && video.videoWidth > 0) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0);
        const image = context.getImageData(0, 0, canvas.width, canvas.height);
        const results = await ZXingWASM.readBarcodes(image, {
          formats,
          tryHarder: true,
          maxNumberOfSymbols: 1,
        });
        const found = results.find((result) => result.isValid);
        if (found) {
          handle(found.text);
        }
      }
      setTimeout(scanFrame, SCAN_INTERVAL_MS);
    }

    scanFrame();
  }

  document.querySelectorAll("[data-scanner]").forEach(start);
})();
