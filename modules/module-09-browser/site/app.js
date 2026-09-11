const shipments = {
  UPS1234567890: {
    carrier: "United Parcel Service (simulated)",
    status: "In transit",
    location: "Columbus, OH",
    estimate: "Tuesday, September 15",
    detail: "Package departed the regional processing facility."
  },
  FDX9876543210: {
    carrier: "FedEx (simulated)",
    status: "Out for delivery",
    location: "Seattle, WA",
    estimate: "Today by 8:00 PM",
    detail: "Package is on the local delivery vehicle."
  },
  UPS0011223344: {
    carrier: "United Parcel Service (simulated)",
    status: "Delivered",
    location: "Austin, TX",
    estimate: "Delivered yesterday",
    detail: "Package was delivered to the front door."
  }
};

const form = document.querySelector("#tracking-form");
const input = document.querySelector("#tracking-number");
const result = document.querySelector("#tracking-result");

function renderShipment(trackingNumber) {
  const normalized = trackingNumber.trim().toUpperCase();
  const shipment = shipments[normalized];
  input.value = trackingNumber.trim();
  result.dataset.loaded = "true";

  if (!shipment) {
    result.innerHTML = `
      <div class="error">No shipment found for <strong>${normalized || "that number"}</strong>.</div>
      <p class="hint">Try UPS1234567890, FDX9876543210, or UPS0011223344.</p>`;
    return;
  }

  result.innerHTML = `
    <div class="status-row"><span class="label">Tracking number</span><strong id="tracking-id">${normalized}</strong></div>
    <div class="status-row"><span class="label">Carrier</span><span id="tracking-carrier">${shipment.carrier}</span></div>
    <div class="status-row"><span class="label">Status</span><strong id="tracking-status">${shipment.status}</strong></div>
    <div class="status-row"><span class="label">Current location</span><span id="tracking-location">${shipment.location}</span></div>
    <div class="status-row"><span class="label">Estimated delivery</span><span id="tracking-estimate">${shipment.estimate}</span></div>
    <p id="tracking-detail" class="detail">${shipment.detail}</p>`;
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const trackingNumber = input.value.trim();
  const url = new URL(window.location.href);
  url.searchParams.set("trackingNumber", trackingNumber);
  window.history.replaceState({}, "", url);
  renderShipment(trackingNumber);
});

const trackingNumber = new URLSearchParams(window.location.search).get("trackingNumber");
if (trackingNumber) renderShipment(trackingNumber);
