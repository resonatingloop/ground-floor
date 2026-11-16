(() => {
  "use strict";

  const study = window.__SETTLEMENT_STUDY__;
  if (!study || !Array.isArray(study.scenarios)) {
    document.body.textContent = "study data could not be loaded";
    return;
  }

  const elements = {
    warning: document.querySelector("[data-warning]"), scenarioNav: document.querySelector("[data-scenario-nav]"),
    observer: document.querySelector("[data-observer]"), condition: document.querySelector("[data-condition]"),
    conditionLabel: document.querySelector("[data-condition-label]"), field: document.querySelector("[data-field]"),
    dependencies: document.querySelector("[data-dependencies]"), returnPath: document.querySelector("[data-return-path]"),
    detail: document.querySelector("[data-detail]"), detailTitle: document.querySelector("[data-detail-title]"),
    trace: document.querySelector("[data-trace]"), readableAccount: document.querySelector("[data-readable-account]"),
    status: document.querySelector("[data-status]")
  };

  const shapes = { introduction: "◇", receipt: "○", admission: "▣", reliance: "◆", challenge: "↯", preservation: "⬡", residue: "⌁" };
  const state = { scenarioIndex: 0, selectedMomentId: study.scenarios[0].moments[0].id, selectedDependencyId: null };
  const make = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const scenario = () => study.scenarios[state.scenarioIndex];
  const momentById = (id) => scenario().moments.find((moment) => moment.id === id);
  const objectById = (id) => scenario().standingObjects.find((object) => object.id === id);
  const dependencyById = (id) => scenario().dependencies.find((dependency) => dependency.id === id);

  function appendDatum(container, label, value, options = {}) {
    const wrapper = make("div", `datum${options.wide ? " wide" : ""}`);
    if (options.definition) wrapper.append(make("dt", "", label), make("dd", "", value));
    else wrapper.append(make("p", "datum-label", label), make("p", "", value));
    container.append(wrapper);
    return wrapper;
  }

  function appendDefinition(list, label, value) {
    const wrapper = make("div", "");
    wrapper.append(make("dt", "", label), make("dd", "", value));
    list.append(wrapper);
  }

  function renderScenarioNav() {
    const buttons = study.scenarios.map((item, index) => {
      const button = make("button", "scenario-button");
      button.type = "button";
      button.dataset.scenarioId = item.id;
      button.setAttribute("aria-pressed", index === state.scenarioIndex ? "true" : "false");
      button.append(make("span", "scenario-number", item.neutralMeta), make("span", "scenario-name", item.neutralLabel));
      button.addEventListener("click", () => selectScenario(index));
      button.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
        event.preventDefault();
        const next = (index + (event.key === "ArrowRight" ? 1 : -1) + study.scenarios.length) % study.scenarios.length;
        selectScenario(next);
        elements.scenarioNav.querySelectorAll("button")[next].focus();
      });
      return button;
    });
    elements.scenarioNav.replaceChildren(...buttons);
  }

  function syncScenarioButtons() {
    elements.scenarioNav.querySelectorAll("[data-scenario-id]").forEach((button, index) => {
      button.setAttribute("aria-pressed", index === state.scenarioIndex ? "true" : "false");
    });
  }

  function renderObserver() {
    elements.observer.replaceChildren();
    for (const [label, value] of Object.entries(scenario().observer)) appendDatum(elements.observer, label, value, { definition: true });
  }

  function renderCondition() {
    const current = scenario().changeCondition;
    elements.conditionLabel.textContent = "read the switch before the verdict";
    elements.condition.replaceChildren();
    appendDatum(elements.condition, "governing priority", current.priority);
    appendDatum(elements.condition, "reverse pressure", current.reversePressure);
    appendDatum(elements.condition, "revision authority", current.revisionAuthority);
    appendDatum(elements.condition, "claim ceiling", current.nonClaim);
    const verdict = appendDatum(elements.condition, "bounded interpretation", current.interpretation, { wide: true });
    verdict.classList.add("condition-verdict");
    verdict.querySelector("p:last-child").prepend(make("strong", "", current.interpretationLabel));
  }

  function buildMomentButton(moment) {
    const button = make("button", "moment-mark");
    button.type = "button";
    button.dataset.momentId = moment.id;
    button.setAttribute("aria-label", `${moment.order}. ${moment.label}; ${moment.layer} layer`);
    button.setAttribute("aria-pressed", moment.id === state.selectedMomentId && !state.selectedDependencyId ? "true" : "false");
    button.append(make("span", "mark-shape", shapes[moment.action] || "□"), make("span", "mark-copy", moment.label));
    button.addEventListener("click", () => selectMoment(moment.id, true));
    return button;
  }

  function renderField() {
    const current = scenario();
    elements.field.style.setProperty("--moment-count", String(current.moments.length));
    const nodes = [make("div", "field-corner", "layer / sequence")];
    current.moments.forEach((moment) => {
      const heading = make("div", "field-time");
      heading.append(make("strong", "", String(moment.order).padStart(2, "0")), document.createTextNode(moment.actor));
      nodes.push(heading);
    });
    study.standingLayers.forEach((layer) => {
      nodes.push(make("div", "layer-label", layer));
      current.moments.forEach((moment) => {
        const cell = make("div", "field-cell");
        if (moment.layer === layer) cell.append(buildMomentButton(moment));
        nodes.push(cell);
      });
    });
    elements.field.replaceChildren(...nodes);
  }

  function renderDependencies() {
    const nodes = scenario().dependencies.map((dependency) => {
      const source = momentById(dependency.sourceMomentId);
      const target = momentById(dependency.targetMomentId);
      const button = make("button", "dependency-button");
      button.type = "button";
      button.dataset.dependencyId = dependency.id;
      button.setAttribute("aria-pressed", dependency.id === state.selectedDependencyId ? "true" : "false");
      button.setAttribute("aria-label", `${dependency.relation}: ${source.label} to ${target.label}`);
      button.append(make("span", "edge-id", source.coldId), make("span", "", dependency.relation), make("span", "edge-arrow", `→ ${target.coldId}`));
      button.addEventListener("click", () => selectDependency(dependency.id, true));
      return button;
    });
    elements.dependencies.replaceChildren(...nodes);
  }

  function renderReturnPath() {
    const nodes = scenario().returnStages.map((stage) => {
      const button = make("button", "return-stage");
      button.type = "button";
      button.dataset.momentId = stage.momentId;
      button.dataset.stageId = stage.id;
      button.setAttribute("aria-pressed", stage.momentId === state.selectedMomentId && !state.selectedDependencyId ? "true" : "false");
      button.setAttribute("aria-label", `${stage.band}; ${stage.role}; ${stage.interpretation}`);
      const node = make("span", "stage-node");
      node.append(make("span", "", String(stage.order).padStart(2, "0")));
      const copy = make("span", "");
      copy.append(make("span", "stage-band", stage.band), make("span", "stage-role", stage.role));
      button.append(node, copy);
      button.addEventListener("click", () => selectMoment(stage.momentId, true));
      return button;
    });
    elements.returnPath.replaceChildren(...nodes);
  }

  function renderTrace() {
    const nodes = scenario().moments.map((moment) => {
      const item = make("li", "");
      const button = make("button", "trace-button");
      button.type = "button";
      button.dataset.momentId = moment.id;
      button.setAttribute("aria-pressed", moment.id === state.selectedMomentId && !state.selectedDependencyId ? "true" : "false");
      button.setAttribute("aria-label", `${moment.order}. ${moment.actor}: ${moment.text}`);
      const copy = make("span", "trace-copy");
      copy.append(make("span", "", moment.text), make("span", "trace-evidence", moment.evidenceClass));
      button.append(make("span", "trace-order", String(moment.order).padStart(2, "0")), make("span", "trace-actor", moment.actor), copy);
      button.addEventListener("click", () => selectMoment(moment.id, true));
      item.append(button);
      return item;
    });
    elements.trace.replaceChildren(...nodes);
  }

  function dependencyDetail(dependency) {
    const source = momentById(dependency.sourceMomentId);
    const target = momentById(dependency.targetMomentId);
    const sourceObject = objectById(dependency.sourceObjectId);
    elements.detailTitle.textContent = `${source.coldId} → ${target.coldId} / ${dependency.relation}`;
    const grid = make("div", "detail-grid");
    appendDatum(grid, "selected object", dependency.id);
    appendDatum(grid, "source → target", `${source.coldId} → ${target.coldId}`);
    appendDatum(grid, "source proposition", sourceObject.proposition, { wide: true });
    appendDatum(grid, "source-object relation", sourceObject.relation);
    appendDatum(grid, "evidence class", dependency.evidenceClass);
    appendDatum(grid, "source-object claim ceiling", sourceObject.claimCeiling, { wide: true });
    const article = make("article", "edge-detail");
    article.append(make("h3", "", dependency.relation));
    const list = make("dl", "");
    appendDefinition(list, "support", dependency.support);
    appendDefinition(list, "live alternative", dependency.alternative);
    appendDefinition(list, "explicit non-claim", dependency.nonClaim);
    appendDefinition(list, "target reference", `${target.coldId}: ${target.label}; the selected object remains this authored relation, not the target moment.`);
    article.append(list);
    elements.detail.replaceChildren(grid, article);
  }

  function momentDetail(moment) {
    const object = objectById(moment.objectId);
    const stage = scenario().returnStages.find((item) => item.momentId === moment.id);
    const related = scenario().dependencies.filter((item) => item.sourceMomentId === moment.id || item.targetMomentId === moment.id);
    elements.detailTitle.textContent = `${String(moment.order).padStart(2, "0")} / ${moment.label}`;
    const grid = make("div", "detail-grid");
    appendDatum(grid, "fictional id", moment.coldId);
    appendDatum(grid, "standing layer", moment.layer);
    appendDatum(grid, "proposition", object.proposition, { wide: true });
    appendDatum(grid, "relation", object.relation);
    appendDatum(grid, "evidence class", moment.evidenceClass);
    appendDatum(grid, "claim ceiling", object.claimCeiling, { wide: true });
    if (stage) appendDatum(grid, "return-path reading", `${stage.role}: ${stage.interpretation}`, { wide: true });
    const edgeNodes = related.map((dependency) => {
      const article = make("article", "edge-detail");
      article.append(make("h3", "", dependency.relation));
      const list = make("dl", "");
      appendDefinition(list, "support", dependency.support);
      appendDefinition(list, "evidence class", dependency.evidenceClass);
      appendDefinition(list, "live alternative", dependency.alternative);
      appendDefinition(list, "explicit non-claim", dependency.nonClaim);
      article.append(list);
      return article;
    });
    if (!edgeNodes.length) edgeNodes.push(make("p", "edge-detail", "no authored dependency terminates at this moment; receipt or admission alone is not consequential standing."));
    elements.detail.replaceChildren(grid, ...edgeNodes);
  }

  function renderDetail() {
    const dependency = dependencyById(state.selectedDependencyId);
    if (dependency) dependencyDetail(dependency);
    else momentDetail(momentById(state.selectedMomentId) || scenario().moments[0]);
  }

  function renderReadableAccount() {
    const current = scenario();
    const heading = make("h3", "", `complete authored account / ${current.neutralLabel}`);
    const aperture = make("dl", "readable-section");
    appendDefinition(aperture, "observer slice", current.observer.slice);
    appendDefinition(aperture, "projection", current.observer.projection);
    appendDefinition(aperture, "attribution", current.observer.attribution);
    appendDefinition(aperture, "occlusion", current.observer.occlusion);
    const conditionHeading = make("h4", "", "change condition");
    const condition = make("dl", "readable-section");
    appendDefinition(condition, "governing priority", current.changeCondition.priority);
    appendDefinition(condition, "reverse pressure", current.changeCondition.reversePressure);
    appendDefinition(condition, "revision authority", current.changeCondition.revisionAuthority);
    appendDefinition(condition, "bounded interpretation", `${current.changeCondition.interpretationLabel}: ${current.changeCondition.interpretation}`);
    appendDefinition(condition, "explicit non-claim", current.changeCondition.nonClaim);
    const dependencyHeading = make("h4", "", "authored dependencies");
    const dependencyList = make("ol", "readable-relations");
    current.dependencies.forEach((dependency) => {
      const source = momentById(dependency.sourceMomentId);
      const target = momentById(dependency.targetMomentId);
      const object = objectById(dependency.sourceObjectId);
      const item = make("li", "");
      const details = make("dl", "readable-section");
      appendDefinition(details, "support", dependency.support);
      appendDefinition(details, "evidence class", dependency.evidenceClass);
      appendDefinition(details, "live alternative", dependency.alternative);
      appendDefinition(details, "source-object claim ceiling", object.claimCeiling);
      appendDefinition(details, "explicit non-claim", dependency.nonClaim);
      item.append(make("strong", "", `${source.coldId} → ${target.coldId}: ${dependency.relation}`), details);
      dependencyList.append(item);
    });
    const returnHeading = make("h4", "", "return-path readings");
    const returnList = make("ol", "readable-relations");
    current.returnStages.forEach((stage) => {
      const moment = momentById(stage.momentId);
      returnList.append(make("li", "", `${stage.order}. ${stage.band}; ${stage.role}; ${moment.coldId}: ${stage.interpretation}`));
    });
    const caveat = make("p", "readable-caveat", "an empty layer cell means only that no relation was authored there; it is not evidence that the layer was examined and found absent.");
    elements.readableAccount.replaceChildren(heading, aperture, conditionHeading, condition, dependencyHeading, dependencyList, returnHeading, returnList, caveat);
  }

  function syncSelection() {
    document.querySelectorAll("[data-moment-id]").forEach((node) => {
      node.setAttribute("aria-pressed", !state.selectedDependencyId && node.dataset.momentId === state.selectedMomentId ? "true" : "false");
    });
    document.querySelectorAll("[data-dependency-id]").forEach((node) => {
      node.setAttribute("aria-pressed", node.dataset.dependencyId === state.selectedDependencyId ? "true" : "false");
    });
  }

  function selectMoment(momentId, announce) {
    if (!momentById(momentId)) return;
    state.selectedMomentId = momentId;
    state.selectedDependencyId = null;
    syncSelection();
    renderDetail();
    if (announce) elements.status.textContent = `selected moment ${momentById(momentId).coldId}: ${momentById(momentId).label}`;
  }

  function selectDependency(dependencyId, announce) {
    const dependency = dependencyById(dependencyId);
    if (!dependency) return;
    state.selectedDependencyId = dependencyId;
    state.selectedMomentId = dependency.targetMomentId;
    syncSelection();
    renderDetail();
    if (announce) elements.status.textContent = `selected relation ${dependency.relation}`;
  }

  function selectScenario(index) {
    if (!study.scenarios[index]) return;
    state.scenarioIndex = index;
    state.selectedMomentId = scenario().moments[0].id;
    state.selectedDependencyId = null;
    syncScenarioButtons();
    renderScenario();
    elements.status.textContent = `showing ${scenario().neutralLabel}; attention reset to the first moment`;
  }

  function renderScenario() {
    renderObserver(); renderCondition(); renderField(); renderDependencies(); renderReturnPath(); renderTrace(); renderReadableAccount(); renderDetail(); syncSelection();
  }

  elements.warning.textContent = study.warning;
  renderScenarioNav();
  renderScenario();
})();
