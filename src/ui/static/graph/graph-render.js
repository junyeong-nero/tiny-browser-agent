// ── d3 graph renderer ──────────────────────────────────
const graph = (() => {
  const svgEl = document.getElementById('graph-svg');
  const wrapEl = document.getElementById('graph-wrap');
  const emptyEl = document.getElementById('graph-empty');
  const breadcrumbEl = document.getElementById('graph-breadcrumb');
  const tooltip = document.getElementById('graph-tooltip');
  const legendEl = document.getElementById('graph-legend');
  const cueLegendEl = document.getElementById('graph-cue-legend');
  const fitBtn = document.getElementById('graph-fit');
  const zoomInBtn = document.getElementById('graph-zoom-in');
  const zoomOutBtn = document.getElementById('graph-zoom-out');

  const svg = d3.select(svgEl);
  const root = svg.append('g').attr('class', 'graph-root');
  const linkG = root.append('g').attr('class', 'links');
  const nodeG = root.append('g').attr('class', 'nodes');
  const GRAPH_TREE_LAYER_SPACING = 96;
  const GRAPH_TREE_SIBLING_SPACING = 118;
  const zoomBehavior = d3.zoom()
    .scaleExtent([0.3, 3])
    .on('zoom', (event) => {
      root.attr('transform', event.transform);
    });

  svg.call(zoomBehavior);

  const simulation = d3.forceSimulation()
    .force('link', d3.forceLink().id(d => d.id).distance(90).strength(1).iterations(4))
    .force('charge', d3.forceManyBody().strength(-160).distanceMax(360))
    .force('center', d3.forceCenter(0, 0).strength(0.05))
    .force('collide', d3.forceCollide(34).strength(1).iterations(2))
    .on('tick', ticked);

  let nodeSel = nodeG.selectAll('g');
  let linkSel = linkG.selectAll('path');
  let nodesData = [];
  let linksData = [];
  let graphMode = 'url';

  function resize() {
    const { width, height } = wrapEl.getBoundingClientRect();
    svgEl.setAttribute('viewBox', `${-width / 2} ${-height / 2} ${width} ${height}`);
    svgEl.setAttribute('width', width);
    svgEl.setAttribute('height', height);
  }
  window.addEventListener('resize', resize);
  resize();

  function graphTransition() {
    return svg.transition().duration(220);
  }

  function zoomBy(factor) {
    graphTransition().call(zoomBehavior.scaleBy, factor);
  }

  function fitToNodes() {
    if (!nodesData.length) {
      graphTransition().call(zoomBehavior.transform, d3.zoomIdentity);
      return;
    }
    const { width, height } = wrapEl.getBoundingClientRect();
    if (!width || !height) return;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    nodesData.forEach(n => {
      const x = Number.isFinite(n.x) ? n.x : n._targetX;
      const y = Number.isFinite(n.y) ? n.y : n._targetY;
      if (!Number.isFinite(x) || !Number.isFinite(y)) return;
      const r = graphNodeRadius(n) + 8;
      if (x - r < minX) minX = x - r;
      if (x + r > maxX) maxX = x + r;
      if (y - r < minY) minY = y - r;
      if (y + r > maxY) maxY = y + r;
    });
    if (!Number.isFinite(minX) || !Number.isFinite(minY)) {
      graphTransition().call(zoomBehavior.transform, d3.zoomIdentity);
      return;
    }
    const boundsWidth = Math.max(1, maxX - minX);
    const boundsHeight = Math.max(1, maxY - minY);
    const padding = 40;
    const scale = Math.max(
      0.3,
      Math.min(3, Math.min((width - padding) / boundsWidth, (height - padding) / boundsHeight))
    );
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    const transform = d3.zoomIdentity
      .translate(-centerX * scale, -centerY * scale)
      .scale(scale);
    graphTransition().call(zoomBehavior.transform, transform);
  }

  if (fitBtn) fitBtn.addEventListener('click', (event) => { event.stopPropagation(); fitToNodes(); });
  if (zoomInBtn) zoomInBtn.addEventListener('click', (event) => { event.stopPropagation(); zoomBy(1.25); });
  if (zoomOutBtn) zoomOutBtn.addEventListener('click', (event) => { event.stopPropagation(); zoomBy(0.8); });

  function ticked() {
    linkSel.attr('d', linkPath);
    nodeSel.attr('transform', d => `translate(${d.x},${d.y})`);
  }

  function rootPosition(index = 0, count = 1) {
    return {
      x: graphMode === 'url' ? (index - (count - 1) / 2) * 140 : 0,
      y: graphMode === 'url' ? -180 : -220,
    };
  }

  function targetX(d) {
    if (d && d.isRoot && d._rootPin) return d._rootPin.x;
    if (d && Number.isFinite(d._targetX)) return d._targetX;
    return 0;
  }

  function targetY(d) {
    if (d && d.isRoot && d._rootPin) return d._rootPin.y;
    if (d && Number.isFinite(d._targetY)) return d._targetY;
    return 90;
  }

  function normalizeGraphNode(src) {
    return {
      isRoot: false,
      isCurrent: false,
      drillable: false,
      ...src,
    };
  }

  function drillAnchorForNode(node) {
    if (graphMode === 'url' || !graphDrillAnchor || !node) return null;
    if (graphDrillAnchor.id !== node.id) return null;
    if (graphDrillAnchor.toLevel !== graphMode) return null;
    if (!Number.isFinite(graphDrillAnchor.x) || !Number.isFinite(graphDrillAnchor.y)) return null;
    return { x: graphDrillAnchor.x, y: graphDrillAnchor.y };
  }

  function linkEndpointId(endpoint) {
    if (endpoint && typeof endpoint === 'object') return endpoint.id;
    return endpoint;
  }

  function isLinearAcyclicGraph(nodes, acyclicLinks) {
    if (linksData.some(e => e.isCycleEdge)) return false;
    if (nodes.length <= 1) return true;
    if (acyclicLinks.length !== nodes.length - 1) return false;
    const ids = new Set(nodes.map(n => n.id));
    const incoming = new Map(nodes.map(n => [n.id, 0]));
    const outgoing = new Map(nodes.map(n => [n.id, 0]));
    acyclicLinks.forEach(link => {
      const sourceId = linkEndpointId(link.source);
      const targetId = linkEndpointId(link.target);
      if (!ids.has(sourceId) || !ids.has(targetId)) return;
      outgoing.set(sourceId, (outgoing.get(sourceId) || 0) + 1);
      incoming.set(targetId, (incoming.get(targetId) || 0) + 1);
    });
    let startCount = 0;
    let endCount = 0;
    for (const node of nodes) {
      const inCount = incoming.get(node.id) || 0;
      const outCount = outgoing.get(node.id) || 0;
      if (inCount > 1 || outCount > 1) return false;
      if (inCount === 0) startCount += 1;
      if (outCount === 0) endCount += 1;
    }
    return startCount === 1 && endCount === 1;
  }

  function buildTopDownLayoutTargets(nodes) {
    const orderedNodes = [...nodes].sort((a, b) => {
      const bySequence = (a._sequenceIndex || 0) - (b._sequenceIndex || 0);
      if (bySequence) return bySequence;
      return String(a.id).localeCompare(String(b.id));
    });
    const topY = graphMode === 'url' ? -180 : -220;
    const acyclicLinks = linksData.filter(e => !e.isCycleEdge);
    if (isLinearAcyclicGraph(orderedNodes, acyclicLinks)) {
      return new Map(orderedNodes.map((node, index) => [node.id, { x: 0, y: topY + index * GRAPH_TREE_LAYER_SPACING }]));
    }

    const nodesById = new Map(orderedNodes.map(node => [node.id, node]));
    const childrenById = new Map(orderedNodes.map(node => [node.id, []]));
    const incomingCount = new Map(orderedNodes.map(node => [node.id, 0]));
    acyclicLinks.forEach(link => {
      const sourceId = linkEndpointId(link.source);
      const targetId = linkEndpointId(link.target);
      if (!nodesById.has(sourceId) || !nodesById.has(targetId) || sourceId === targetId) return;
      childrenById.get(sourceId).push(targetId);
      incomingCount.set(targetId, (incomingCount.get(targetId) || 0) + 1);
    });
    childrenById.forEach(children => {
      children.sort((a, b) => {
        const left = nodesById.get(a);
        const right = nodesById.get(b);
        return (left._sequenceIndex || 0) - (right._sequenceIndex || 0);
      });
    });

    const roots = orderedNodes.filter(node => (incomingCount.get(node.id) || 0) === 0);
    const queue = (roots.length ? roots : orderedNodes.slice(0, 1)).map(node => ({ id: node.id, depth: 0 }));
    const depthById = new Map();
    while (queue.length) {
      const current = queue.shift();
      if (depthById.has(current.id) && depthById.get(current.id) <= current.depth) continue;
      depthById.set(current.id, current.depth);
      for (const childId of childrenById.get(current.id) || []) {
        queue.push({ id: childId, depth: current.depth + 1 });
      }
    }
    orderedNodes.forEach((node, index) => {
      if (!depthById.has(node.id)) depthById.set(node.id, index);
    });

    const levels = new Map();
    orderedNodes.forEach(node => {
      const depth = depthById.get(node.id) || 0;
      if (!levels.has(depth)) levels.set(depth, []);
      levels.get(depth).push(node);
    });

    const targets = new Map();
    Array.from(levels.keys()).sort((a, b) => a - b).forEach(depth => {
      const levelNodes = levels.get(depth).sort((a, b) => {
        const bySequence = (a._sequenceIndex || 0) - (b._sequenceIndex || 0);
        if (bySequence) return bySequence;
        return String(a.id).localeCompare(String(b.id));
      });
      levelNodes.forEach((node, index) => {
        targets.set(node.id, {
          x: (index - (levelNodes.length - 1) / 2) * GRAPH_TREE_SIBLING_SPACING,
          y: topY + depth * GRAPH_TREE_LAYER_SPACING,
        });
      });
    });
    return targets;
  }

  function arrangeGraphNodes(nodes, previousById) {
    const rootNodes = nodes.filter(n => n.isRoot);
    const layoutTargets = buildTopDownLayoutTargets(nodes);
    const pinRoots = graphMode !== 'url';
    const rootsById = new Map(rootNodes.map((node, index) => {
      const pinned = drillAnchorForNode(node) || rootPosition(index, rootNodes.length);
      const target = layoutTargets.get(node.id) || pinned;
      node._targetX = target.x;
      node._targetY = target.y;
      if (pinRoots) {
        node._rootPin = pinned;
        node.fx = pinned.x;
        node.fy = pinned.y;
      } else {
        node._rootPin = null;
        node.fx = null;
        node.fy = null;
      }
      if (!previousById.has(node.id) || !Number.isFinite(node.x) || !Number.isFinite(node.y)) {
        node.x = target.x;
        node.y = target.y;
      }
      return [node.id, node];
    }));
    nodes.filter(n => !n.isRoot).forEach((node) => {
      node.fx = null;
      node.fy = null;
      const target = layoutTargets.get(node.id) || { x: 0, y: 90 };
      node._targetX = target.x;
      node._targetY = target.y;
      if (previousById.has(node.id) && Number.isFinite(node.x) && Number.isFinite(node.y)) return;
      node.x = target.x;
      node.y = target.y;
    });
  }

  function linkPath(d) {
    const source = d.source || {};
    const target = d.target || {};
    const sx = source.x || 0;
    const sy = source.y || 0;
    const tx = target.x || 0;
    const ty = target.y || 0;
    if ((source.id || source) === (target.id || target)) {
      const r = 22 + Math.min(14, Math.log2((d.count || 1) + 1) * 4);
      return `M ${sx} ${sy - 8} C ${sx + r} ${sy - r * 1.6}, ${sx + r * 1.8} ${sy + r * 1.2}, ${sx + 4} ${sy + 8}`;
    }
    const dx = tx - sx;
    const dy = ty - sy;
    const dist = Math.hypot(dx, dy) || 1;
    const ux = dx / dist;
    const uy = dy / dist;
    const sourceR = (typeof source === 'object' && source) ? graphNodeRadius(source) : 7;
    const targetR = (typeof target === 'object' && target) ? graphNodeRadius(target) : 7;
    const x1 = sx + ux * sourceR;
    const y1 = sy + uy * sourceR;
    const x2 = tx - ux * targetR;
    const y2 = ty - uy * targetR;
    return `M ${x1} ${y1} L ${x2} ${y2}`;
  }

  function showTooltip(event, d) {
    const rows = [];
    const title = d.label || d.host || d.actionName || d.id;
    rows.push(`<div class="tt-row"><span>level</span><span class="v">${escHtml(d.type || '—')}</span></div>`);
    if (d.isStart && d.isEnd) rows.push(`<div class="tt-row"><span>flow</span><span class="v">start & end</span></div>`);
    else if (d.isStart) rows.push(`<div class="tt-row"><span>flow</span><span class="v">start ▶</span></div>`);
    else if (d.isEnd) rows.push(`<div class="tt-row"><span>flow</span><span class="v">end ■</span></div>`);
    if (d.actionStepCount != null) rows.push(`<div class="tt-row"><span>total steps</span><span class="v">${d.actionStepCount}</span></div>`);
    if (d.actionCount != null) rows.push(`<div class="tt-row"><span>unique actions</span><span class="v">${d.actionCount}</span></div>`);
    if (d.visits != null) rows.push(`<div class="tt-row"><span>visits</span><span class="v">${d.visits}</span></div>`);
    if (d.drillable) rows.push(`<div class="tt-row"><span>double-click</span><span class="v">drill in</span></div>`);
    const cueRows = [];
    if (d && d.ownCues) {
      const own = d.ownCues;
      const inside = d.rollupBreakdown || { cycle: 0, repeated: 0, noop: 0, deadEnd: 0 };
      const cueLabels = { cycle: 'cycle', repeated: 'repeated', noop: 'no-op', deadEnd: 'dead end' };
      for (const cueType of ['cycle', 'repeated', 'noop', 'deadEnd']) {
        const ownN = own[cueType] ? 1 : 0;
        const insideN = inside[cueType] || 0;
        if (ownN || insideN) {
          cueRows.push(`<div class="tt-row"><span>${cueLabels[cueType]}</span><span class="v">${ownN} own / ${insideN} inside</span></div>`);
        }
      }
    }
    const cueSection = cueRows.length
      ? `<div class="tt-section">Cues</div>` + cueRows.join('')
      : '';
    tooltip.innerHTML = `<div class="tt-url">${escHtml(title)}</div>` + rows.join('') + cueSection;
    tooltip.classList.remove('hidden');
    moveTooltip(event);
  }
  function moveTooltip(event) {
    const rect = wrapEl.getBoundingClientRect();
    const x = event.clientX - rect.left + 14;
    const y = event.clientY - rect.top + 14;
    const maxX = rect.width - tooltip.offsetWidth - 10;
    const maxY = rect.height - tooltip.offsetHeight - 10;
    tooltip.style.left = Math.max(6, Math.min(x, maxX)) + 'px';
    tooltip.style.top  = Math.max(6, Math.min(y, maxY)) + 'px';
  }
  function hideTooltip() { tooltip.classList.add('hidden'); }

  function graphNodeWorkCount(d) {
    if (!d) return 0;
    if (Number.isFinite(d.actionStepCount)) return d.actionStepCount;
    if (Array.isArray(d.stepIds) && d.stepIds.length) return d.stepIds.length;
    if (Number.isFinite(d.actionCount)) return d.actionCount;
    return Number.isFinite(d.visits) ? d.visits : 0;
  }

  function trajectoryMaxWorkCount() {
    let max = 0;
    trajectoryNodes.forEach(url => {
      const count = actionStepCountForActionIds(url.actionIds);
      if (count > max) max = count;
    });
    return max;
  }

  function graphNodeRadius(d) {
    const base = 7;
    const count = graphNodeWorkCount(d);
    return base + Math.min(9, Math.log2((count || 1) + 1) * 1.8);
  }

  function levelEndpointShape(d) {
    if (!d || (!d.isStart && !d.isEnd)) return '';
    const r = graphNodeRadius(d);
    if (d.isStart && d.isEnd) {
      const s = r * 1.25;
      return `M 0 ${-s} L ${s} 0 L 0 ${s} L ${-s} 0 Z`;
    }
    if (d.isStart) {
      const w = r * 1.35;
      const h = r * 1.15;
      return `M ${-w * 0.65} ${-h} L ${w} 0 L ${-w * 0.65} ${h} Z`;
    }
    const s = r * 1.05;
    return `M ${-s} ${-s} L ${s} ${-s} L ${s} ${s} L ${-s} ${s} Z`;
  }

  function graphNodeFill(d, maxWorkCount) {
    const count = graphNodeWorkCount(d);
    if (!count || !maxWorkCount) return d3.interpolateViridis(0.12);
    const normalized = Math.sqrt(Math.min(count, maxWorkCount) / maxWorkCount);
    const t = 0.12 + normalized * 0.82;
    return d3.interpolateViridis(t);
  }

  function updateGraphLegend(maxWorkCount, hasNodes) {
    if (legendEl) {
      if (!hasNodes) legendEl.classList.add('hidden');
      else {
        const roundedMaxWorkCount = Math.round(Number(maxWorkCount) || 0);
        const maxLabel = legendEl.querySelector('[data-legend-max]');
        if (maxLabel) maxLabel.textContent = `${roundedMaxWorkCount}`;
        legendEl.classList.remove('hidden');
      }
    }
    if (cueLegendEl) cueLegendEl.classList.toggle('hidden', !hasNodes);
  }

  function drag() {
    return d3.drag()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x; d.fy = d.y;
      })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        if (d.isRoot) {
          if (d._rootPin) {
            d.fx = d._rootPin.x;
            d.fy = d._rootPin.y;
          } else {
            d.fx = null;
            d.fy = null;
          }
          return;
        }
        d.fx = null; d.fy = null;
      });
  }

  function layerName(level) {
    if (level === 'action') return 'Action layer';
    if (level === 'viewport') return 'Viewport layer';
    return 'URL layer';
  }

  function renderBreadcrumb(payload) {
    const crumbs = (payload && payload.breadcrumb) || [];
    const parts = [];
    crumbs.forEach((crumb, idx) => {
      parts.push(`<button type="button" data-idx="${idx}">${escHtml(layerName(crumb.level))}</button>`);
      parts.push('<span class="sep">›</span>');
    });
    const parentLabel = payload && payload.parentLabel && payload.mode !== 'url' ? payload.parentLabel : null;
    parts.push(`<span class="current-layer">${escHtml(layerName(payload.mode))}</span>`);
    if (parentLabel) parts.push(`<span class="parent-label">inside ${escHtml(parentLabel)}</span>`);
    breadcrumbEl.innerHTML = parts.join('');
    breadcrumbEl.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', () => {
        const crumb = crumbs[Number(btn.dataset.idx || 0)];
        if (!crumb || crumb.level === 'url') {
          setGraphDrilldown({ level: 'url', urlId: null, viewportId: null });
        } else if (crumb.level === 'viewport') {
          setGraphDrilldown({ level: 'viewport', urlId: crumb.urlId, viewportId: null });
        }
      });
    });
  }

  function update(payload) {
    // Badges encode the dominant hidden lower-layer cue type (color + glyph).
    // Own-layer cues are rendered through their primary visual channels instead
    // of being duplicated in a badge.
    function cueBadgeClass(d) {
      if (!d || !(d.badgeCount > 0)) return { circleClass: null, textClass: null, glyph: '', hidden: true };
      const rollupType = dominantRollupCueType(d);
      if (rollupType) {
        return {
          circleClass: `rollup-red cue-${rollupType}`,
          textClass: 'on-stroke',
          glyph: CUE_GLYPH[rollupType] || '',
          hidden: false,
        };
      }
      return { circleClass: null, textClass: null, glyph: '', hidden: true };
    }

    graphMode = payload.mode || 'url';
    emptyEl.textContent = payload.mode === 'url' ? 'no navigation yet.' : 'no child nodes yet.';
    renderBreadcrumb(payload);
    const levelEl = document.getElementById('graph-level');
    const nodeCountEl = document.getElementById('graph-node-count');
    const edgeCountEl = document.getElementById('graph-edge-count');
    if (levelEl)     levelEl.textContent = payload.mode === 'url' ? 'URLs' : (payload.mode === 'viewport' ? 'viewports' : 'actions');
    if (nodeCountEl) nodeCountEl.textContent = String((payload.nodes || []).length);
    if (edgeCountEl) edgeCountEl.textContent = String((payload.links || []).length);

    const previousNodeIds = new Set(nodesData.map(n => n.id));
    const previousLinkKeys = new Set(linksData.map(e => `${edgeEndpointId(e.source)}|${edgeEndpointId(e.target)}`));
    const incomingNodes = payload.nodes || [];
    const incomingLinks = payload.links || [];
    const structureChanged = incomingNodes.length !== nodesData.length ||
      incomingLinks.length !== linksData.length ||
      incomingNodes.some(n => !previousNodeIds.has(n.id)) ||
      incomingLinks.some(e => !previousLinkKeys.has(`${edgeEndpointId(e.source)}|${edgeEndpointId(e.target)}`));

    const prevById = new Map(nodesData.map(n => [n.id, n]));
    nodesData = incomingNodes.map(src => {
      const prev = prevById.get(src.id);
      return Object.assign(prev || {}, normalizeGraphNode(src));
    });
    linksData = incomingLinks.map(e => ({ ...e }));
    arrangeGraphNodes(nodesData, prevById);
    const maxWorkCount = Math.max(1, trajectoryMaxWorkCount(), ...nodesData.map(graphNodeWorkCount));
    updateGraphLegend(maxWorkCount, nodesData.length > 0);

    emptyEl.style.display = nodesData.length ? 'none' : 'flex';

    linkSel = linkG.selectAll('path.graph-link').data(linksData, d =>
      (d.source.id || d.source) + '|' + (d.target.id || d.target)
    );
    linkSel.exit().remove();
    linkSel = linkSel.enter().append('path').attr('class', 'graph-link').merge(linkSel);
    linkSel
      .classed('cycle', d => !!d.isCycleEdge)
      .attr('stroke-width', d => {
        const count = d.count || 1;
        const extra = 1.5 * Math.log2(count);
        return d.isCycleEdge ? Math.min(8, 2 + extra) : Math.min(6, 1 + extra);
      });

    nodeSel = nodeG.selectAll('g.graph-node').data(nodesData, d => d.id);
    nodeSel.exit().remove();
    const enter = nodeSel.enter().append('g')
      .attr('class', 'graph-node')
      .call(drag())
      .on('click', (event, d) => { event.stopPropagation(); selectGraphNode(d); })
      .on('dblclick', (event, d) => { event.stopPropagation(); hideTooltip(); drillGraphNode(d); })
      .on('mouseenter', showTooltip)
      .on('mousemove', moveTooltip)
      .on('mouseleave', hideTooltip);
    enter.append('circle').attr('r', 8);
    // Cue-ring: outer stroke that carries the dominant cue color so the node's
    // viridis frequency fill stays readable underneath (outline §S2).
    enter.append('circle').attr('class', 'cue-ring').attr('r', 8);
    enter.append('path').attr('class', 'graph-node-shape');
    enter.append('text').attr('class', 'graph-node-label').attr('dx', 12).attr('dy', 4);
    const badgeEnter = enter.append('g').attr('class', 'node-cue-badge');
    badgeEnter.append('circle').attr('r', 8);
    badgeEnter.append('text');
    nodeSel = enter.merge(nodeSel);
    nodeSel
      .classed('root', d => d.isRoot)
      .classed('url', d => d.type === 'url')
      .classed('viewport', d => d.type === 'viewport')
      .classed('action', d => d.type === 'action')
      .classed('drillable', d => !!d.drillable)
      .classed('current', d => !!d.isCurrent)
      .classed('running', d => isRunningGraphNode(d))
      .classed('selected', d => d.id === selectedNodeId)
      .classed('start', d => !!d.isStart)
      .classed('end', d => !!d.isEnd)
      .style('--graph-node-fill', d => graphNodeFill(d, maxWorkCount));
    nodeSel.select('circle:not(.cue-ring)').attr('r', d => graphNodeRadius(d));
    nodeSel.select('circle.cue-ring').each(function(d) {
      const sel = d3.select(this);
      const cueType = ownCueRingType(d);
      const baseR = graphNodeRadius(d);
      sel.attr('r', baseR + 3)
        .attr('class', cueType ? `cue-ring cue-${cueType}` : 'cue-ring')
        .style('display', cueType ? null : 'none');
    });
    nodeSel.select('path.graph-node-shape')
      .attr('d', d => levelEndpointShape(d))
      .style('display', d => (d.isStart || d.isEnd) ? null : 'none');
    nodeSel.select('text.graph-node-label').text(displayGraphNodeLabel);
    const badgeSel = nodeSel.select('g.node-cue-badge');
    badgeSel.each(function(d) {
      const sel = d3.select(this);
      const meta = cueBadgeClass(d);
      if (meta.hidden) {
        sel.style('display', 'none');
        return;
      }
      sel.style('display', null);
      const r = graphNodeRadius(d);
      sel.attr('transform', `translate(${r + 4},${-(r + 4)})`);
      // Glyph alone for badgeCount=1; glyph+count when ≥2 so reviewers see how
      // many child cues rolled up without losing the cue-type signal.
      const label = d.badgeCount >= 2 ? `${meta.glyph}${d.badgeCount}` : meta.glyph;
      sel.select('circle')
        .attr('class', meta.circleClass)
        .attr('r', d.badgeCount >= 10 ? 10 : 8);
      sel.select('text')
        .attr('class', meta.textClass)
        .text(label);
    });

    simulation.nodes(nodesData);
    simulation.force('link').links(linksData);
    if (structureChanged) {
      simulation.alpha(1);
      for (let i = 0; i < 300; i++) simulation.tick();
      simulation.alpha(0);
      ticked();
    } else {
      simulation.alpha(Math.max(simulation.alpha(), 0.06)).restart();
    }
  }


  function reset() {
    nodesData = [];
    linksData = [];
    graphRenderDirty = false;
    linkG.selectAll('*').remove();
    nodeG.selectAll('*').remove();
    hideTooltip();
    updateGraphLegend(1, false);
    breadcrumbEl.innerHTML = '<span>URL layer</span>';
    emptyEl.style.display = 'flex';
    emptyEl.textContent = 'no navigation yet.';
    simulation.nodes([]);
    simulation.force('link').links([]);
  }

  function refreshSelection() {
    nodeG.selectAll('g.graph-node').classed('selected', d => d.id === selectedNodeId);
  }

  function refreshRunning() {
    nodeG.selectAll('g.graph-node').classed('running', d => isRunningGraphNode(d));
  }

  svg.on('click', () => clearGraphSelection());

  return { update, reset, resize, refreshSelection, refreshRunning, fitToNodes };
})();

function isGraphViewActive() {
  return document.body.classList.contains('view-graph');
}

function updateGraph({ force = false } = {}) {
  if (!force && !isGraphViewActive()) {
    graphRenderDirty = true;
    return;
  }
  graphRenderDirty = false;
  graph.update(selectedGraphData());
}

function scheduleGraphUpdate() {
  updateGraph();
}

function resetGraph()  { resetTrajectoryGraphState(); clearGraphSelection(); graphRenderDirty = false; graph.reset(); }
function resizeGraph() { graph.resize(); }

window.updateGraph = updateGraph;
window.resetGraph = resetGraph;
window.resizeGraph = resizeGraph;
window.clearGraphSelection = clearGraphSelection;
window.selectGraphActionForStep = selectGraphActionForStep;
window.recordActionExecution = recordActionExecution;
window.setGraphRunningStep = setGraphRunningStep;
window.clearGraphRunningStep = clearGraphRunningStep;
window.setTrajectoryOutcome = setTrajectoryOutcome;
window.actionNodeForStep = actionNodeForStep;
window.hydrateNoopEvidence = hydrateNoopEvidence;
