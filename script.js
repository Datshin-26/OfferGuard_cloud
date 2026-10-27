const offerForm = document.getElementById("offerForm");
const statusMessage = document.getElementById("status");
let history = [];

offerForm.addEventListener("submit", checkOffer);

async function checkOffer(event) {
    event.preventDefault();
    setStatus("Checking offer and saving to CSV...");

    const offer = {
        company: document.getElementById("company").value.trim(),
        website: document.getElementById("website").value.trim(),
        email: document.getElementById("email").value.trim(),
        fee: document.getElementById("fee").value,
        message: document.getElementById("message").value.trim()
    };

    try {
        const response = await fetch("/api/verifications", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(offer)
        });
        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "Could not save this offer check.");
        }

        showResult(result);
        await loadHistory();
        setStatus("Offer checked and saved to data/verifications.csv.");
    } catch (error) {
        setStatus(error.message, true);
    }
}

function showResult(result) {
    document.getElementById("resultCard").style.display = "block";
    document.getElementById("riskLevel").textContent = result.risk;
    document.getElementById("riskScore").textContent =
        `Risk Score: ${result.score}/100`;

    const reasonsDiv = document.getElementById("reasons");
    reasonsDiv.replaceChildren();

    const reasons = result.reasons.length
        ? result.reasons
        : ["No suspicious patterns detected. Independently verify the company and offer."];

    reasons.forEach(reason => {
        const paragraph = document.createElement("p");
        paragraph.textContent = reason;
        reasonsDiv.appendChild(paragraph);
    });

    reasonsDiv.appendChild(document.createTextNode(
        "This score is only a heuristic estimate, not proof of authenticity."
    ));
}

async function loadHistory() {
    const response = await fetch("/api/verifications");
    const result = await response.json();

    if (!response.ok) {
        throw new Error(result.error || "Could not load saved verification history.");
    }

    history = result;
    displayHistory();
}

function displayHistory() {
    const historyDiv = document.getElementById("history");
    historyDiv.replaceChildren();

    if (history.length === 0) {
        historyDiv.textContent = "No verification history yet.";
        return;
    }

    history.forEach(item => {
        const entry = document.createElement("div");
        entry.className = "history-item";
        entry.textContent = [
            item.company,
            item.risk,
            `${item.score}/100`,
            new Date(item.date).toLocaleString()
        ].join(" | ");
        historyDiv.appendChild(entry);
    });
}

function setStatus(message, isError = false) {
    statusMessage.textContent = message;
    statusMessage.classList.toggle("error", isError);
}

loadHistory().catch(error => {
    setStatus(error.message, true);
});
