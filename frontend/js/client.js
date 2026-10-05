/**
 * Client Dashboard Logic
 * 
 * Handles: project creation, viewing own projects, ranked bid lists,
 * bid acceptance, project completion, and freelancer rating.
 */

document.addEventListener('DOMContentLoaded', () => {
  if (!requireAuth('client')) return;

  // Set navbar user info
  document.getElementById('nav-username').textContent = getUsername();
  document.getElementById('nav-avatar').textContent = avatarInitials(getUsername());

  initTabs();
  initModals();
  loadStats();
  loadMyProjects();
  setupCreateProjectForm();
  setupRatingForm();
});

// --- Stats ---

async function loadStats() {
  const res = await projectsAPI.my();
  if (!res.ok) return;

  const projects = res.data;
  const open = projects.filter(p => p.status === 'open').length;
  const inProgress = projects.filter(p => p.status === 'in_progress').length;
  const completed = projects.filter(p => p.status === 'completed').length;
  const totalBids = projects.reduce((sum, p) => sum + (p.bid_count || 0), 0);

  document.getElementById('stat-open').textContent = open;
  document.getElementById('stat-progress').textContent = inProgress;
  document.getElementById('stat-completed').textContent = completed;
  document.getElementById('stat-bids').textContent = totalBids;
}

// --- My Projects ---

async function loadMyProjects() {
  const container = document.getElementById('projects-list');
  container.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';

  const res = await projectsAPI.my();
  if (!res.ok) {
    container.innerHTML = `<div class="empty-state"><p>${res.error}</p></div>`;
    return;
  }

  const projects = res.data;
  if (projects.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📋</div>
        <p>No projects yet. Post your first project!</p>
        <button class="btn btn-primary" onclick="openModal('create-project-modal')">+ New Project</button>
      </div>`;
    return;
  }

  container.innerHTML = projects.map((p, i) => `
    <div class="glass-card project-card animate-in animate-in-delay-${Math.min(i, 4)}" data-id="${p.id}">
      <div class="project-header">
        <div>
          <h3 class="project-title">${escapeHTML(p.title)}</h3>
          <p class="project-description">${escapeHTML(p.description || '')}</p>
        </div>
        ${statusBadge(p.status)}
      </div>
      <div class="flex-gap">
        ${skillChipsHTML(p.required_skills || [])}
      </div>
      <div class="project-meta">
        <span>💰 ${formatCurrency(p.budget_min)} – ${formatCurrency(p.budget_max)}</span>
        <span>📅 ${formatDate(p.deadline)}</span>
        <span>📨 ${p.bid_count || 0} bids</span>
      </div>
      <div class="flex-between mt-sm">
        ${p.bid_count > 0 ? `<button class="btn btn-secondary btn-sm" onclick="viewBids(${p.id})">View Ranked Bids</button>` : '<span></span>'}
        ${p.status === 'in_progress' ? `<button class="btn btn-primary btn-sm" onclick="completeProject(${p.id})">
          ${p.client_completed ? '✓ Waiting for freelancer' : 'Mark Complete'}
        </button>` : ''}
        ${p.status === 'completed' && !p.rated ? `<button class="btn btn-gold btn-sm" onclick="openRatingModal(${p.id})">★ Rate Freelancer</button>` : ''}
      </div>
    </div>
  `).join('');
}

// --- View Ranked Bids ---

async function viewBids(projectId) {
  const modal = document.getElementById('bids-modal');
  const container = document.getElementById('bids-list');
  container.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';
  openModal('bids-modal');

  // Fetch project details for skill matching context
  const projRes = await projectsAPI.get(projectId);
  const project = projRes.ok ? projRes.data : null;

  const res = await bidsAPI.listRanked(projectId);
  if (!res.ok) {
    container.innerHTML = `<div class="empty-state"><p>${res.error}</p></div>`;
    return;
  }

  const bids = res.data;
  if (bids.length === 0) {
    container.innerHTML = '<div class="empty-state"><p>No bids yet.</p></div>';
    return;
  }

  // Store project ID for accept action
  modal.dataset.projectId = projectId;

  container.innerHTML = bids.map((bid, i) => `
    <div class="bid-card animate-in animate-in-delay-${Math.min(i, 4)}">
      <div class="rank-badge ${rankClass(bid.rank)}">${bid.rank}</div>
      <div class="score-circle ${scoreClass(bid.match_score)}">
        ${Math.round(bid.match_score * 100)}
      </div>
      <div class="bid-info">
        <div class="bid-freelancer">
          <span>${escapeHTML(bid.freelancer_name)}</span>
          ${starDisplayHTML(bid.freelancer_rating || 0)}
        </div>
        <div class="bid-amount">${formatCurrency(bid.amount)}</div>
        ${bid.proposal ? `<p class="bid-proposal">${escapeHTML(bid.proposal)}</p>` : ''}
        <div class="flex-gap mt-sm">
          ${skillChipsHTML(bid.freelancer_skills || [], project?.required_skills || [])}
        </div>
        ${scoreBreakdownHTML(bid.match_score)}
      </div>
      ${project?.status === 'open' ? `
        <button class="btn btn-primary btn-sm" onclick="acceptBid(${projectId}, ${bid.bid_id})">
          Accept
        </button>
      ` : ''}
    </div>
  `).join('');

  animateScoreBars();
}

// --- Accept Bid ---

async function acceptBid(projectId, bidId) {
  if (!confirm('Accept this bid? The project will move to "In Progress".')) return;

  const res = await projectsAPI.acceptBid(projectId, bidId);
  if (res.ok) {
    showToast('Bid accepted! Project is now in progress.', 'success');
    closeModal('bids-modal');
    loadMyProjects();
    loadStats();
  } else {
    showToast(res.error, 'error');
  }
}

// --- Complete Project ---

async function completeProject(projectId) {
  const res = await projectsAPI.complete(projectId);
  if (res.ok) {
    if (res.data.status === 'completed') {
      showToast('Project marked as completed!', 'success');
    } else {
      showToast('Your confirmation recorded. Waiting for the other party.', 'info');
    }
    loadMyProjects();
    loadStats();
  } else {
    showToast(res.error, 'error');
  }
}

// --- Create Project ---

function setupCreateProjectForm() {
  const form = document.getElementById('create-project-form');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const skillsRaw = document.getElementById('proj-skills').value;
    const skills = skillsRaw.split(',').map(s => s.trim()).filter(s => s);

    const body = {
      title: document.getElementById('proj-title').value,
      description: document.getElementById('proj-desc').value,
      required_skills: skills,
      budget_min: parseFloat(document.getElementById('proj-budget-min').value),
      budget_max: parseFloat(document.getElementById('proj-budget-max').value),
      deadline: new Date(document.getElementById('proj-deadline').value).toISOString(),
    };

    const res = await projectsAPI.create(body);
    if (res.ok) {
      showToast('Project posted successfully!', 'success');
      closeModal('create-project-modal');
      form.reset();
      loadMyProjects();
      loadStats();
    } else {
      showToast(res.error, 'error');
    }
  });
}

// --- Rating ---

let ratingProjectId = null;

function openRatingModal(projectId) {
  ratingProjectId = projectId;
  openModal('rating-modal');
  initStarRatings();
}

function setupRatingForm() {
  const form = document.getElementById('rating-form');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const starEl = document.querySelector('#rating-modal .star-rating');
    const score = parseInt(starEl?.dataset.rating || '0');
    if (score < 1 || score > 5) {
      showToast('Please select a star rating (1-5)', 'error');
      return;
    }

    const review = document.getElementById('rating-review').value;

    const res = await projectsAPI.rate(ratingProjectId, { score, review });
    if (res.ok) {
      showToast('Rating submitted! Thank you.', 'success');
      closeModal('rating-modal');
      form.reset();
      loadMyProjects();
    } else {
      showToast(res.error, 'error');
    }
  });
}

// --- Utility ---

function escapeHTML(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
