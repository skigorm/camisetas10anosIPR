// 3D shirt viewer: builds a volumetric shirt from the silhouette of the front texture
// and wraps the front/back artwork around it. Loaded on demand by app.js.
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.min.js';

const GRID = 220;          // vertices along the shirt height
const DEPTH = 0.1;       // half thickness of the torso, in shirt heights
const EDGE = 0.09;         // how far in from the outline the surface reaches full depth

let renderer, scene, camera, shirt, host, frame, onFace;
let angle = 0, target = null, velocity = 0, auto = true, drag = null, lastTime = 0;
const cache = new Map();

const loadImage = src => new Promise((ok, fail) => { const i = new Image(); i.onload = () => ok(i); i.onerror = fail; i.src = src; });

function silhouette(img) {
  const ny = GRID, nx = Math.round(GRID * img.width / img.height);
  const c = document.createElement('canvas'); c.width = nx; c.height = ny;
  const g = c.getContext('2d', { willReadFrequently: true }); g.drawImage(img, 0, 0, nx, ny);
  const data = g.getImageData(0, 0, nx, ny).data, inside = new Uint8Array(nx * ny);
  for (let i = 0; i < nx * ny; i++) inside[i] = data[i * 4 + 3] > 235;
  // chamfer distance to the outline, in grid cells
  const d = new Float32Array(nx * ny).fill(1e9), D = 1, DD = Math.SQRT2;
  for (let i = 0; i < nx * ny; i++) if (!inside[i]) d[i] = 0;
  for (let y = 0; y < ny; y++) for (let x = 0; x < nx; x++) {
    const i = y * nx + x; if (!d[i]) continue;
    if (x) d[i] = Math.min(d[i], d[i - 1] + D);
    if (y) { d[i] = Math.min(d[i], d[i - nx] + D); if (x) d[i] = Math.min(d[i], d[i - nx - 1] + DD); if (x < nx - 1) d[i] = Math.min(d[i], d[i - nx + 1] + DD); }
  }
  for (let y = ny - 1; y >= 0; y--) for (let x = nx - 1; x >= 0; x--) {
    const i = y * nx + x; if (!d[i]) continue;
    if (x < nx - 1) d[i] = Math.min(d[i], d[i + 1] + D);
    if (y < ny - 1) { d[i] = Math.min(d[i], d[i + nx] + D); if (x < nx - 1) d[i] = Math.min(d[i], d[i + nx + 1] + DD); if (x) d[i] = Math.min(d[i], d[i + nx - 1] + DD); }
  }
  // soften the chamfer steps so the outline does not show a staircase from the side
  for (let pass = 0; pass < 3; pass++) {
    const s = d.slice();
    for (let y = 1; y < ny - 1; y++) for (let x = 1; x < nx - 1; x++) {
      const i = y * nx + x; if (!inside[i]) continue;
      d[i] = (s[i] * 4 + s[i - 1] + s[i + 1] + s[i - nx] + s[i + nx]) / 8;
    }
  }
  return { nx, ny, inside, d };
}

function surface({ nx, ny, inside, d }, side) {
  const w = nx / ny, R = EDGE * ny, pos = [], uv = [], idx = [], map = new Int32Array(nx * ny).fill(-1);
  const used = new Uint8Array(nx * ny);
  for (let y = 0; y < ny - 1; y++) for (let x = 0; x < nx - 1; x++) {
    const a = y * nx + x;
    if (inside[a] || inside[a + 1] || inside[a + nx] || inside[a + nx + 1]) used[a] = used[a + 1] = used[a + nx] = used[a + nx + 1] = 1;
  }
  // grow the mesh a little past the outline: the texture's own alpha trims it precisely
  for (let pass = 0; pass < 2; pass++) {
    const s = used.slice();
    for (let y = 1; y < ny - 1; y++) for (let x = 1; x < nx - 1; x++) { const i = y * nx + x; if (s[i - 1] || s[i + 1] || s[i - nx] || s[i + nx]) used[i] = 1; }
  }
  for (let y = 0; y < ny; y++) for (let x = 0; x < nx; x++) {
    const i = y * nx + x; if (!used[i]) continue;
    const t = Math.min(Math.max(d[i] - 1.5, 0) / R, 1), profile = Math.sqrt(1 - (1 - t) * (1 - t));
    const u = x / (nx - 1), v = y / (ny - 1);
    // a little extra roundness across the chest so it does not look like a pillow
    const belly = 0.35 * (1 - Math.min(1, ((u - 0.5) / 0.32) ** 2)) * Math.min(Math.max(d[i] - 1.5, 0) / (R * 2.5), 1);
    map[i] = pos.length / 3;
    pos.push((u - 0.5) * w, 0.5 - v, side * DEPTH * (profile + belly));
    uv.push(side >= 0 ? u : 1 - u, 1 - v);
  }
  for (let y = 0; y < ny - 1; y++) for (let x = 0; x < nx - 1; x++) {
    const a = map[y * nx + x], b = map[y * nx + x + 1], c = map[(y + 1) * nx + x], e = map[(y + 1) * nx + x + 1];
    if (a < 0 || b < 0 || c < 0 || e < 0) continue;
    if (side >= 0) idx.push(a, c, b, b, c, e); else idx.push(a, b, c, b, e, c);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  geo.setIndex(idx); geo.computeVertexNormals();
  return geo;
}

function texture(img) {
  const t = new THREE.Texture(img);
  t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = renderer.capabilities.getMaxAnisotropy(); t.needsUpdate = true;
  return t;
}

function material(map) {
  // the photos already carry the fabric's shading, so most of the colour is emitted as-is
  // and the scene lights only add the shading that changes while it turns
  return new THREE.MeshLambertMaterial({ map, emissiveMap: map, emissive: 0xffffff, emissiveIntensity: 0.62, alphaTest: 0.5, alphaToCoverage: true, side: THREE.FrontSide });
}

async function build(front, back) {
  const key = front + '|' + back;
  if (!cache.has(key)) cache.set(key, Promise.all([loadImage(front), loadImage(back)]).then(([fi, bi]) => {
    const sil = silhouette(fi), group = new THREE.Group();
    group.add(new THREE.Mesh(surface(sil, 1), material(texture(fi))));
    group.add(new THREE.Mesh(surface(sil, -1), material(texture(bi))));
    // flat inner layer along the side seams, so no background shows where front and back meet
    const inner = new THREE.Mesh(surface(sil, 0), new THREE.MeshBasicMaterial({ map: group.children[0].material.map, alphaTest: 0.5, side: THREE.DoubleSide }));
    group.add(inner);
    return group;
  }));
  return cache.get(key);
}

const MIN_ZOOM = 1, MAX_ZOOM = 3.2, START_ZOOM = 1.18;
let baseDistance = 3, zoom = START_ZOOM, zoomTarget = START_ZOOM, pan = 0;
const pointers = new Map();
let pinch = null;

function resize() {
  const { clientWidth: w, clientHeight: h } = host;
  if (!w || !h) return;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  // fit the shirt (about 1 unit tall and up to 1 unit wide) in view
  const fitH = 1.28, fitW = 1.15 / camera.aspect;
  baseDistance = Math.max(fitH, fitW) / 2 / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) + DEPTH;
  camera.updateProjectionMatrix();
}

// how far the view may move up or down at the current zoom (the shirt is 1 unit tall)
const panLimit = () => Math.max(0, 0.5 - 0.5 / zoom + 0.04);

function tick(time) {
  frame = requestAnimationFrame(tick);
  const dt = Math.min((time - (lastTime || time)) / 1000, 0.05); lastTime = time;
  if (target !== null) { angle += (target - angle) * Math.min(1, dt * 7); if (Math.abs(target - angle) < 0.001) { angle = target; target = null; } }
  else if (!drag) { if (Math.abs(velocity) > 0.01) { angle += velocity * dt; velocity *= Math.pow(0.04, dt); } else if (auto) angle += dt * 0.35; }
  zoom += (zoomTarget - zoom) * Math.min(1, dt * 10);
  pan = THREE.MathUtils.clamp(pan, -panLimit(), panLimit());
  camera.position.set(0, pan + 0.04, baseDistance / zoom);
  camera.lookAt(0, pan, 0);
  if (shirt) shirt.rotation.y = angle;
  onFace?.(Math.cos(angle) < 0);
  renderer.render(scene, camera);
}

export function zoomBy(factor) {
  zoomTarget = THREE.MathUtils.clamp(zoomTarget * factor, MIN_ZOOM, MAX_ZOOM);
  auto = false;
}

function setup(container) {
  host = container;
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.domElement.className = 'viewer-canvas';
  host.append(renderer.domElement);
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(28, 1, 0.1, 20);
  scene.add(new THREE.HemisphereLight(0xffffff, 0xd9cfc0, 0.9));
  const key = new THREE.DirectionalLight(0xffffff, 1.1); key.position.set(1.5, 1.2, 2.5); scene.add(key);
  const rim = new THREE.DirectionalLight(0xffffff, 0.8); rim.position.set(-1.5, 1, -2.5); scene.add(rim);
  new ResizeObserver(resize).observe(host);
  const el = renderer.domElement;
  el.addEventListener('wheel', e => { e.preventDefault(); zoomBy(Math.exp(-e.deltaY * 0.0015)); }, { passive: false });
  el.addEventListener('pointerdown', e => {
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    el.setPointerCapture(e.pointerId);
    auto = false; target = null; velocity = 0;
    if (pointers.size === 2) {
      const [p, q] = [...pointers.values()];
      pinch = { dist: Math.hypot(p.x - q.x, p.y - q.y), zoom: zoomTarget }; drag = null;
    } else if (pointers.size === 1) drag = { x: e.clientX, y: e.clientY, t: performance.now(), moved: false };
  });
  el.addEventListener('pointermove', e => {
    if (!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pinch && pointers.size === 2) {
      const [p, q] = [...pointers.values()];
      zoomTarget = THREE.MathUtils.clamp(pinch.zoom * Math.hypot(p.x - q.x, p.y - q.y) / pinch.dist, MIN_ZOOM, MAX_ZOOM);
      return;
    }
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y, now = performance.now();
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) drag.moved = true;
    angle += dx * 0.011; velocity = dx * 0.011 / Math.max((now - drag.t) / 1000, 0.008);
    // vertical drag moves along the shirt when zoomed in
    const visible = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.position.z;
    pan += dy / el.clientHeight * visible;
    drag.x = e.clientX; drag.y = e.clientY; drag.t = now;
  });
  const end = e => {
    pointers.delete(e.pointerId);
    if (pinch) { if (pointers.size < 2) pinch = null; drag = null; return; }
    if (!drag) return;
    const tapped = !drag.moved; if (performance.now() - drag.t > 80) velocity = 0; drag = null;
    if (tapped) showSide(Math.cos(angle) > 0);
  };
  el.addEventListener('pointerup', end); el.addEventListener('pointercancel', end);
}

export function showSide(back) {
  auto = false; velocity = 0;
  const turn = Math.round(angle / (2 * Math.PI)) * 2 * Math.PI;
  const options = back ? [turn - Math.PI, turn + Math.PI] : [turn];
  target = options.reduce((a, b) => Math.abs(b - angle) < Math.abs(a - angle) ? b : a);
}

export async function open(container, front, back, faceCallback) {
  if (!renderer) setup(container);
  onFace = faceCallback;
  const group = await build(front, back);
  if (shirt) scene.remove(shirt);
  shirt = group; scene.add(shirt);
  angle = -0.5; target = 0; auto = true; velocity = 0; zoom = zoomTarget = START_ZOOM; pan = 0;
  resize();
  cancelAnimationFrame(frame); lastTime = 0; frame = requestAnimationFrame(tick);
  // keep spinning slowly once the opening turn finishes, until the visitor takes over
  setTimeout(() => { if (target === null && !drag) auto = true; }, 900);
}

export function close() { cancelAnimationFrame(frame); }

export function supported() {
  try { return !!document.createElement('canvas').getContext('webgl2'); } catch { return false; }
}
