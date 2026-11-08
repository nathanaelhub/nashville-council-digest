// "Which district am I in?": look a street address up in Metro's public parcel
// layer (the same one the build uses to place bills) and link to that district.
// Only the address, city, ZIP and council district are requested: no owner data.
const PARCELS = "https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/Parcels_view/FeatureServer/0/query";
const SUFFIX = {
  street: "ST", st: "ST", avenue: "AVE", ave: "AVE", road: "RD", rd: "RD", drive: "DR", dr: "DR",
  pike: "PIKE", lane: "LN", ln: "LN", boulevard: "BLVD", blvd: "BLVD", court: "CT", ct: "CT",
  place: "PL", pl: "PL", way: "WAY", circle: "CIR", cir: "CIR", parkway: "PKWY", pkwy: "PKWY",
  trail: "TRL", trl: "TRL", highway: "HWY", hwy: "HWY", terrace: "TER", ter: "TER", square: "SQ", sq: "SQ",
  pass: "PASS", cove: "CV", cv: "CV", run: "RUN", loop: "LOOP", row: "ROW", alley: "ALY", bend: "BND",
};
const DIRECTION = { north: "N", south: "S", east: "E", west: "W", n: "N", s: "S", e: "E", w: "W" };
const NEAR = 200; // how far a house number may be from the closest one on file

// "1 Public Square, Nashville TN 37201" -> {house: "1", street: "PUBLIC%SQ", zip: "37201"}
function parse(text) {
  const zip = (text.match(/\b(37\d{3})(?:-\d{4})?\s*$/) || [])[1] || "";
  const first = text.split(",")[0].replace(/[^\w\s]/g, " ").trim().toUpperCase();
  const m = first.match(/^(\d{1,6})[A-Z]?\s+(.+)$/);
  if (!m) return null;
  const words = m[2].split(/\s+/);
  let dir = "";
  if (words.length > 1 && DIRECTION[words.at(-1).toLowerCase()]) dir = DIRECTION[words.pop().toLowerCase()];
  const suffix = words.length > 1 ? SUFFIX[words.at(-1).toLowerCase()] : undefined;
  if (suffix) words.pop();
  const street = [...words, ...(suffix ? [suffix] : []), ...(dir ? [dir] : [])].join("%").replace(/'/g, "''");
  return { house: m[1], street, zip };
}

// Parcel streets are stored like "WEST END  AVE" or "MAIN  ST N": match the
// street exactly, or followed by a direction the person left out.
function where(p, extra) {
  const clauses = [`(PropStreet LIKE '${p.street}' OR PropStreet LIKE '${p.street} %')`, extra];
  if (p.zip) clauses.push(`PropZip = '${p.zip}'`);
  return clauses.join(" AND ");
}

async function query(sql) {
  const params = new URLSearchParams({ where: sql, outFields: "PropAddr,PropHouse,PropCity,PropZip,Council", returnGeometry: "false", f: "json" });
  const r = await fetch(`${PARCELS}?${params}`);
  const d = await r.json();
  if (d.error) throw new Error(d.error.message || "parcel query failed");
  return (d.features || []).map((f) => f.attributes).filter((a) => /^\d+$/.test(a.Council || "") && +a.Council >= 1 && +a.Council <= 35);
}

// One entry per distinct place (district, ZIP), so "100 Main St" in two parts
// of the county is shown as two answers instead of being silently merged.
function places(rows) {
  const seen = new Map();
  for (const r of rows) {
    const key = `${+r.Council} ${r.PropZip}`;
    if (!seen.has(key)) seen.set(key, { district: +r.Council, addr: r.PropAddr, city: r.PropCity, zip: r.PropZip });
  }
  return [...seen.values()].sort((a, b) => a.district - b.district);
}

// The exact house number first; otherwise the closest number on the same
// street (within NEAR, per ZIP), as the build does for addresses newer than the
// parcel layer.
async function lookup(text) {
  const p = parse(text);
  if (!p) return { error: "Type a street address with a house number, like 1 Public Square." };
  let rows = await query(where(p, `PropHouse = '${p.house}'`));
  let near = false;
  if (!rows.length) {
    const h = parseInt(p.house, 10);
    const street = await query(where(p, `PropHouse <> '' AND PropHouse <> '0' AND CAST(PropHouse AS INT) BETWEEN ${Math.max(1, h - NEAR)} AND ${h + NEAR}`));
    const best = new Map();
    for (const r of street) {
      const d = Math.abs(+r.PropHouse - h);
      if (!best.has(r.PropZip) || d < best.get(r.PropZip).d) best.set(r.PropZip, { d, r });
    }
    rows = [...best.values()].map((x) => x.r);
    near = true;
  }
  const found = places(rows);
  if (!found.length) return { error: "That address wasn't found in Metro's parcel map. Check the spelling, or add the street type (St, Ave, Pike)." };
  return { places: found, near };
}

function link(d) {
  const a = document.createElement("a");
  a.href = `district/${d}.html`;
  a.textContent = `District ${d}`;
  return a;
}

const box = typeof document !== "undefined" && document.getElementById("lookup");
if (box) {
  const out = document.getElementById("lookup-result");
  box.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const text = box.address.value.trim();
    if (!text) return;
    out.textContent = "Looking up…";
    try {
      const r = await lookup(text);
      out.replaceChildren();
      if (r.error) { out.textContent = r.error; return; }
      const [one] = r.places;
      if (r.places.length === 1) {
        out.append(r.near ? `The closest address on file is ${one.addr}, in ` : `${one.addr} is in `, link(one.district), ".");
        return;
      }
      out.append(r.near ? "The closest addresses on file are in more than one part of the county:" : "That address is in more than one part of the county:");
      const ul = document.createElement("ul");
      for (const x of r.places) {
        const li = document.createElement("li");
        li.append(`${x.addr}, ${x.city} ${x.zip}: `, link(x.district));
        ul.append(li);
      }
      out.append(ul, "Add your ZIP code to narrow it down.");
    } catch {
      out.textContent = "Metro's parcel map didn't answer. Try again in a moment.";
    }
  });
}

if (typeof module !== "undefined") module.exports = { parse, where, places, lookup };
