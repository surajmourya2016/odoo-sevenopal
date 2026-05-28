/** @odoo-module **/

/**
 * SevenOpal product configurator.
 * Fixes:
 *  - No duplicate Loose Gemstone (ornaments come only from the loop now)
 *  - Price updates live when certification / design is selected
 *  - Metal options, design grid, ring size show/hide correctly
 */

document.addEventListener("DOMContentLoaded", () => {
    if (!document.querySelector(".js_sale.o_wsale_product_page")) return;

    captureBasePrice();
    initCertification();
    initOrnamentSelector();
    hookAddToCart();

    // Auto-init first ornament card state (it's pre-selected by template)
    const firstCard = document.querySelector(".so_ornament_card.so_ornament_card_active");
    if (firstCard) applyOrnamentCard(firstCard);
});

// ─── Base price ───────────────────────────────────────────────────────────────

let _basePriceRaw = 0;   // numeric value
let _currencySymbol = "";

function captureBasePrice() {
    // Odoo renders the price in span.oe_price — read its text and parse
    const priceEl = document.querySelector("span.oe_price");
    if (!priceEl) return;
    const text = priceEl.textContent.trim();
    // Extract currency symbol (non-digit/non-space/non-comma/non-period prefix or suffix)
    _currencySymbol = text.replace(/[\d,. ]/g, "").trim() || "₹";
    // Parse numeric value
    _basePriceRaw = parseFloat(text.replace(/[^\d.]/g, "")) || 0;
}

// ─── State ────────────────────────────────────────────────────────────────────

const state = {
    certificateId:    null,
    certificateCharge: 0,
    ornamentId:       null,
    metalOptionId:    null,
    metalDesignId:    null,
    metalDesignPrice: 0,
    ringSize:         null,
    ringSizeSystem:   "indian",
};

// ─── Certification ────────────────────────────────────────────────────────────

function initCertification() {
    const select = document.querySelector("select.so_certificate_select");
    if (!select) return;
    select.addEventListener("change", () => {
        const opt = select.options[select.selectedIndex];
        state.certificateId    = opt.value || null;
        state.certificateCharge = parseFloat(opt.dataset.charge || 0);
        refreshPriceDisplay();
    });
}

// ─── Ornament Selector ────────────────────────────────────────────────────────

function initOrnamentSelector() {
    const cards = document.querySelectorAll(".so_ornament_card");
    if (!cards.length) return;

    cards.forEach((card) => {
        card.addEventListener("click", () => {
            cards.forEach((c) => c.classList.remove("so_ornament_card_active"));
            card.classList.add("so_ornament_card_active");
            const radio = card.querySelector("input.so_ornament_radio");
            if (radio) radio.checked = true;
            applyOrnamentCard(card);
        });
    });

    // Metal dropdown → load designs
    const metalSelect = document.querySelector("select.so_metal_select");
    if (metalSelect) {
        metalSelect.addEventListener("change", () => {
            const metalId = parseInt(metalSelect.value || 0);
            state.metalOptionId = metalId || null;
            if (metalId) {
                loadDesigns(metalId);
            } else {
                clearDesigns();
            }
        });
    }

    // Ring size selectors
    const ringSizeEl       = document.querySelector(".so_ring_size");
    const ringSizeSystemEl = document.querySelector(".so_ring_size_system");
    if (ringSizeEl)       ringSizeEl.addEventListener("change",       () => { state.ringSize       = ringSizeEl.value || null; });
    if (ringSizeSystemEl) ringSizeSystemEl.addEventListener("change", () => { state.ringSizeSystem = ringSizeSystemEl.value; });
}

function applyOrnamentCard(card) {
    const ornamentId   = parseInt(card.dataset.ornamentId || 0);
    state.ornamentId   = ornamentId || null;

    // Update label
    const labelSpan = card.querySelector("span");
    const labelEl   = document.querySelector(".so_ornament_label");
    if (labelEl && labelSpan) labelEl.textContent = labelSpan.textContent.trim();

    const enableMetal    = card.dataset.enableMetal    === "1";
    const enableRingSizer = card.dataset.enableRingSizer === "1";

    // Show/hide metal section
    toggleSection(".so_metal_section",    enableMetal);
    toggleSection(".so_design_section",   false);
    toggleSection(".so_ring_size_section", enableRingSizer);

    if (enableMetal && ornamentId) {
        filterMetalOptions(ornamentId);
    } else {
        clearDesigns();
        state.metalOptionId = null;
        state.metalDesignId = null;
        state.metalDesignPrice = 0;
    }
    refreshPriceDisplay();
}

function toggleSection(selector, show) {
    const el = document.querySelector(selector);
    if (!el) return;
    el.classList[show ? "remove" : "add"]("d-none");
}

function filterMetalOptions(ornamentId) {
    const metalSelect = document.querySelector("select.so_metal_select");
    if (!metalSelect) return;
    metalSelect.value    = "";
    state.metalOptionId  = null;

    Array.from(metalSelect.querySelectorAll("option.so_metal_opt")).forEach((opt) => {
        const show = parseInt(opt.dataset.ornamentId) === ornamentId;
        opt.classList[show ? "remove" : "add"]("d-none");
        if (show) opt.removeAttribute("disabled");
        else      opt.setAttribute("disabled", "disabled");
    });

    // Auto-select first visible metal option
    const firstVisible = Array.from(metalSelect.querySelectorAll("option.so_metal_opt"))
        .find((o) => !o.classList.contains("d-none"));
    if (firstVisible) {
        metalSelect.value   = firstVisible.value;
        state.metalOptionId = parseInt(firstVisible.value);
        loadDesigns(state.metalOptionId);
    } else {
        clearDesigns();
    }
}

// ─── Design grid ──────────────────────────────────────────────────────────────

async function loadDesigns(metalOptionId) {
    const grid = document.getElementById("so_design_grid");
    if (!grid) return;

    toggleSection(".so_design_section", true);
    grid.innerHTML = '<div class="col-12 py-3 text-center"><i class="fa fa-spinner fa-spin text-muted"></i></div>';

    try {
        const resp    = await fetch(`/sevenopal/designs/${metalOptionId}`);
        const designs = await resp.json();

        grid.innerHTML = "";
        if (!designs.length) {
            grid.innerHTML = '<div class="col-12 text-muted small">No designs available.</div>';
            return;
        }

        designs.forEach((d, idx) => {
            const col     = document.createElement("div");
            col.className = "col-4 col-md-3";
            const isFirst = idx === 0;
            col.innerHTML = `
                <label class="so_design_card w-100" data-design-id="${d.id}" data-price="${d.price}">
                    <input type="radio" name="_so_design_radio" value="${d.id}" class="d-none"${isFirst ? " checked" : ""}/>
                    <div class="so_design_card_inner${isFirst ? " so_design_card_active" : ""}">
                        ${d.image
                            ? `<img src="/web/image/sevenopal.metal.design/${d.id}/image" alt="${escHtml(d.name)}" class="so_design_img"/>`
                            : `<div class="so_design_img_placeholder"><i class="fa fa-gem fa-2x"></i></div>`}
                        <div class="so_design_name small mt-1">${escHtml(d.description || d.name)}</div>
                        ${d.price ? `<div class="so_design_price small fw-bold" style="color:#c0392b;">+₹${d.price.toLocaleString("en-IN")}</div>` : ""}
                    </div>
                </label>`;
            grid.appendChild(col);

            col.querySelector("input[type=radio]").addEventListener("change", () => {
                grid.querySelectorAll(".so_design_card_inner").forEach((el) => el.classList.remove("so_design_card_active"));
                col.querySelector(".so_design_card_inner").classList.add("so_design_card_active");
                setSelectedDesign(d.id, d.price);
            });
        });

        if (designs.length) setSelectedDesign(designs[0].id, designs[0].price);

    } catch (e) {
        grid.innerHTML = '<div class="col-12 text-danger small">Could not load designs.</div>';
    }
}

function setSelectedDesign(id, price) {
    state.metalDesignId    = id;
    state.metalDesignPrice = parseFloat(price) || 0;
    refreshPriceDisplay();
}

function clearDesigns() {
    const grid = document.getElementById("so_design_grid");
    if (grid) grid.innerHTML = "";
    toggleSection(".so_design_section", false);
    state.metalDesignId    = null;
    state.metalDesignPrice = 0;
    refreshPriceDisplay();
}

// ─── Live price display ───────────────────────────────────────────────────────

function refreshPriceDisplay() {
    const totalRow     = document.querySelector(".so_total_price_row");
    const basePriceEl  = document.querySelector(".so_base_price_display");
    const extrasEl     = document.querySelector(".so_extras_breakdown");
    const totalEl      = document.querySelector(".so_total_price_display");

    const extras = [];
    if (state.certificateCharge > 0) {
        extras.push({ label: "Certificate", amount: state.certificateCharge });
    }
    if (state.metalDesignPrice > 0) {
        extras.push({ label: "Design", amount: state.metalDesignPrice });
    }

    const totalExtra = extras.reduce((s, e) => s + e.amount, 0);

    if (!totalRow) return;

    if (totalExtra === 0) {
        totalRow.classList.add("d-none");
        return;
    }

    totalRow.classList.remove("d-none");

    if (basePriceEl) {
        basePriceEl.textContent = formatPrice(_basePriceRaw);
    }

    if (extrasEl) {
        extrasEl.innerHTML = extras.map((e) =>
            `<div class="d-flex justify-content-between align-items-center mt-1">
                <span class="text-muted small">+ ${escHtml(e.label)}</span>
                <span class="small text-warning">+${formatPrice(e.amount)}</span>
            </div>`
        ).join("");
    }

    if (totalEl) {
        totalEl.textContent = formatPrice(_basePriceRaw + totalExtra);
    }
}

function formatPrice(amount) {
    // Use INR formatting: ₹1,500 style
    return "₹" + amount.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

// ─── Add to cart hook ─────────────────────────────────────────────────────────

function hookAddToCart() {
    document.addEventListener("cart:updated", async (ev) => {
        const lineId = ev.detail && ev.detail.line_id;
        if (!lineId) return;
        if (!hasSevenopalOptions()) return;

        try {
            await jsonrpc("/sevenopal/update_line", {
                line_id:          lineId,
                certificate_id:   state.certificateId   ? parseInt(state.certificateId) : null,
                ornament_id:      state.ornamentId,
                metal_option_id:  state.metalOptionId,
                metal_design_id:  state.metalDesignId,
                ring_size:        state.ringSize,
                ring_size_system: state.ringSizeSystem,
            });
        } catch (e) {
            console.warn("[SevenOpal] Could not update cart line:", e);
        }
    });
}

function hasSevenopalOptions() {
    return !!(state.certificateId || state.ornamentId || state.metalOptionId || state.metalDesignId);
}

// ─── JSON-RPC helper ──────────────────────────────────────────────────────────

async function jsonrpc(url, params) {
    const csrf = document.querySelector('input[name="csrf_token"]')?.value || "";
    const resp = await fetch(url, {
        method:  "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body:    JSON.stringify({ jsonrpc: "2.0", method: "call", id: Date.now(), params }),
    });
    const data = await resp.json();
    if (data.error) throw new Error(data.error.message || "RPC error");
    return data.result;
}

// ─── Product detail tabs ──────────────────────────────────────────────────────

window.soTabSwitch = function (btn, targetId) {
    // Deactivate all tab buttons
    document.querySelectorAll(".so_detail_tab_btn").forEach((b) =>
        b.classList.remove("so_detail_tab_active")
    );
    btn.classList.add("so_detail_tab_active");

    // Show/hide tab content sections
    const allPanels = document.querySelectorAll(".so_tab_content_panel");
    allPanels.forEach((p) => p.classList.add("d-none"));
    const target = document.getElementById(targetId);
    if (target) target.classList.remove("d-none");
};

// On load: wrap existing sections in tab panels
document.addEventListener("DOMContentLoaded", () => {
    const specsSection  = document.querySelector(".so_product_details_table");
    const descSection   = document.querySelector("#product_details .accordion");
    const reviewSection = document.querySelector("#product_details .o_wsale_reviews");

    if (!specsSection && !descSection) return; // not a product detail page

    // Create tab panels if tab nav is present
    if (!document.querySelector(".so_detail_tabs_nav")) return;

    const wrap = (el, id, hidden) => {
        if (!el) return;
        const div = document.createElement("div");
        div.id = id;
        div.className = "so_tab_content_panel" + (hidden ? " d-none" : "");
        el.parentNode.insertBefore(div, el);
        div.appendChild(el);
    };

    // Wrap Product Details (specs) table
    if (specsSection) wrap(specsSection, "so_tab_specs", false);

    // Wrap accordion description block
    if (descSection) {
        wrap(descSection, "so_tab_desc", true);
    }

    // Wrap reviews
    if (reviewSection) wrap(reviewSection, "so_tab_reviews", true);
});

// ─── Homepage tabs ────────────────────────────────────────────────────────────

(function initHomepageTabs() {
    const tabBtns = document.querySelectorAll(".so_tab_btn");
    if (!tabBtns.length) return;

    tabBtns.forEach((btn) => {
        btn.addEventListener("click", () => {
            // Deactivate all
            tabBtns.forEach((b) => b.classList.remove("so_tab_btn_active"));
            document.querySelectorAll(".so_tab_panel").forEach((p) => p.classList.add("d-none"));

            // Activate clicked
            btn.classList.add("so_tab_btn_active");
            const panel = document.getElementById("so_tab_" + btn.dataset.tab);
            if (panel) panel.classList.remove("d-none");
        });
    });
})();

// ─── Weight filter (shop sidebar) ────────────────────────────────────────────

(function initWeightFilter() {
    const btn = document.querySelector(".so_apply_weight_filter");
    if (!btn) return;

    btn.addEventListener("click", function () {
        const minCarat = document.querySelector(".so_min_carat")?.value.trim() || "";
        const maxCarat = document.querySelector(".so_max_carat")?.value.trim() || "";
        const minRatti = document.querySelector(".so_min_ratti")?.value.trim() || "";
        const maxRatti = document.querySelector(".so_max_ratti")?.value.trim() || "";

        const url = new URL(window.location.href);
        const params = url.searchParams;

        minCarat ? params.set("min_carat", minCarat) : params.delete("min_carat");
        maxCarat ? params.set("max_carat", maxCarat) : params.delete("max_carat");
        minRatti ? params.set("min_ratti", minRatti) : params.delete("min_ratti");
        maxRatti ? params.set("max_ratti", maxRatti) : params.delete("max_ratti");

        window.location.href = url.toString();
    });

    // Re-populate inputs from URL params on load
    const params = new URLSearchParams(window.location.search);
    const minCarat = document.querySelector(".so_min_carat");
    const maxCarat = document.querySelector(".so_max_carat");
    const minRatti = document.querySelector(".so_min_ratti");
    const maxRatti = document.querySelector(".so_max_ratti");
    if (minCarat && params.get("min_carat")) minCarat.value = params.get("min_carat");
    if (maxCarat && params.get("max_carat")) maxCarat.value = params.get("max_carat");
    if (minRatti && params.get("min_ratti")) minRatti.value = params.get("min_ratti");
    if (maxRatti && params.get("max_ratti")) maxRatti.value = params.get("max_ratti");
})();

// ─── Utility ──────────────────────────────────────────────────────────────────

function escHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
