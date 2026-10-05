/**
 * Freelancer Dashboard Logic
 * 
 * Handles: browsing open projects, submitting bids, viewing own bids,
 * managing profile (skills + hourly rate), and completing projects.
 */

document.addEventListener('DOMContentLoaded', () => {
  if (!requireAuth('freelancer')) return;

  // Set navbar user info
  document.getElementById('nav-username').textContent = getUsername();
  document.getElementById('nav-avatar').textContent = avatarInitials(getUsername());

  initTabs();
  initModals();
  loadProfile();
  loadStats();
  loadOpenProjects();
  loadMyBids();
  setupProfileForm();
  setupBidForm();
});

// --- Profile ---

let currentProfile = null;

async function loadProfile() {
  const res = await freelancersAPI.myProfile();
  if (res.ok) {
    currentProfile = res.data;
    renderProfileCard();
  }
}

function renderProfileCard() {
  const el = document.getElementById('profile-card');
  if (!el || !currentProfile) return;

  el.innerHTML = `
    <div class="flex-between mb-md">
      <div>
        <h3>${getUsername()}</h3>
        <p class="text-secondary text-sm">Freelancer</p>
      </div>
      <button class="btn btn-secondary btn-sm" onclick="openModal('profile-modal')">Edit Profile</button>
    </div>
    <div class="mb-md">
      <span class="text-muted text-xs">HOURLY RATE</span>
      <p class="budget-display">${formatCurrency(currentProfile.hourly_rate)}/hr</p>
    </div>
    <div class="mb-md">
      <span class="text-muted text-xs">RATING</span>
      <div class="flex-gap" style="align-items: center; gap: 0.5rem;">
        ${starDisplayHTML(currentProfile.avg_rating || 0)}
        <span class="text-sm text-secondary">${(currentProfile.avg_rating || 0).toFixed(1)} (${currentProfile.total_ratings || 0} reviews)</span>
      </div>
    </div>
    <div>
      <span class="text-muted text-xs">SKILLS</span>
      <div class="flex-gap mt-sm">
        ${currentProfile.skills.length > 0
          ? skillChipsHTML(currentProfile.skills)
          : '<span class="text-muted text-sm">No skills added yet</span>'
        }
      </div>
    </div>
  `;
}

// --- Stats ---

async function loadStats() {
  const bidsRes = await bidsAPI.myBids();
  const bids = bidsRes.ok ? bidsRes.data : [];

  document.getElementById('stat-bids').textContent = bids.length;

  // Count active (bids on in_progress projects)
  // For simplicity, show total bids and we'll enrich later
  const projectIds = [...new Set(bids.map(b => b.project_id))];
  let active = 0;
  let completed = 0;
  let earned = 0;

  for (const pid of projectIds) {
    const pRes = await projectsAPI.get(pid);
    if (pRes.ok) {
      if (pRes.data.status === 'in_progress' && pRes.data.accepted_bid_id) {
        const acceptedBid = bids.find(b => b.id === pRes.data.accepted_bid_id);
        if (acceptedBid) { active++; earned += acceptedBid.amount; }
      }
      if (pRes.data.status === 'completed' && pRes.data.accepted_bid_id) {
        const acceptedBid = bids.find(b => b.id === pRes.data.accepted_bid_id);
        if (acceptedBid) { completed++; earned += acceptedBid.amount; }
      }
    }
  }

  document.getElementById('stat-active').textContent = active;
  document.getElementById('stat-completed').textContent = completed;
  document.getElementById('stat-earned').textContent = formatCurrency(earned);
}

// --- Browse Open Projects ---

async function loadOpenProjects() {
  const container = document.getElementById('open-projects-list');
  container.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';

  const res = await projectsAPI.listAll();
  if (!res.ok) {
    container.innerHTML = `<div class="empty-state"><p>${res.error}</p></div>`;
    return;
  }

  const projects = res.data;
  if (projects.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🔍</div>
        <p>No open projects at the moment. Check back soon!</p>
      </div>`;
    return;
  }

  container.innerHTML = projects.map((p, i) => `
    <div class="glass-card project-card animate-in animate-in-delay-${Math.min(i, 4)}">
      <div class="project-header">
        <div>
          <h3 class="project-title">${escapeHTML(p.title)}</h3>
          <span class="text-sm text-muted">by ${escapeHTML(p.client_name || 'Client')}</span>
        </div>
        ${statusBadge(p.status)}
      </div>
      <p class="project-description">${escapeHTML(p.description || 'No description provided.')}</p>
      <div class="flex-gap">
        ${skillChipsHTML(p.required_skills || [], currentProfile?.skills || [])}
      </div>
      <div class="project-meta">
        <span>💰 ${formatCurrency(p.budget_min)} – ${formatCurrency(p.budget_max)}</span>
        <span>📅 ${formatDate(p.deadline)}</span>
        <span>📨 ${p.bid_count || 0} bids</span>
      </div>
      <div>
        <button class="btn btn-primary btn-sm" onclick="openBidModal(${p.id}, '${escapeHTML(p.title)}', ${p.budget_min}, ${p.budget_max})">
          Submit Bid
        </button>
      </div>
    </div>
  `).join('');
}

// --- Submit Bid ---

let bidProjectId = null;

function openBidModal(projectId, title, budgetMin, budgetMax) {
  bidProjectId = projectId;
  document.getElementById('bid-project-title').textContent = title;
  document.getElementById('bid-budget-range').textContent =
    `${formatCurrency(budgetMin)} – ${formatCurrency(budgetMax)}`;
  openModal('bid-modal');
}

function setupBidForm() {
  const form = document.getElementById('bid-form');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const body = {
      amount: parseFloat(document.getElementById('bid-amount').value),
      proposal: document.getElementById('bid-proposal').value,
    };

    const res = await bidsAPI.submit(bidProjectId, body);
    if (res.ok) {
      showToast(`Bid submitted! Match score: ${Math.round(res.data.match_score * 100)}%`, 'success');
      closeModal('bid-modal');
      form.reset();
      loadOpenProjects();
      loadMyBids();
      loadStats();
    } else {
      showToast(res.error, 'error');
    }
  });
}

// --- My Bids ---

async function loadMyBids() {
  const container = document.getElementById('my-bids-list');
  container.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';

  const res = await bidsAPI.myBids();
  if (!res.ok) {
    container.innerHTML = `<div class="empty-state"><p>${res.error}</p></div>`;
    return;
  }

  const bids = res.data;
  if (bids.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📝</div>
        <p>No bids yet. Browse open projects and submit your first bid!</p>
      </div>`;
    return;
  }

  // Fetch project info for each bid
  const bidCards = [];
  for (const bid of bids) {
    const pRes = await projectsAPI.get(bid.project_id);
    const project = pRes.ok ? pRes.data : null;

    const isAccepted = project?.accepted_bid_id === bid.id;
    let bidStatus = 'pending';
    if (project?.status === 'completed' && isAccepted) bidStatus = 'completed';
    else if (project?.status === 'in_progress' && isAccepted) bidStatus = 'in-progress';
    else if (project?.status !== 'open' && !isAccepted) bidStatus = 'not selected';

    bidCards.push(`
      <div class="glass-card animate-in" style="padding: var(--space-lg);">
        <div class="flex-between mb-md">
          <div>
            <h3 class="text-sm fw-600">${escapeHTML(project?.title || `Project #${bid.project_id}`)}</h3>
            <span class="text-xs text-muted">${formatDate(bid.created_at)}</span>
          </div>
          <div style="text-align: right;">
            <div class="bid-amount">${formatCurrency(bid.amount)}</div>
            <div class="score-circle ${scoreClass(bid.match_score)}" style="width: 36px; height: 36px; font-size: 0.75rem; display: inline-flex; margin-top: 0.25rem;">
              ${Math.round(bid.match_score * 100)}
            </div>
          </div>
        </div>
        ${bid.proposal ? `<p class="text-sm text-secondary mb-md">${escapeHTML(bid.proposal)}</p>` : ''}
        <div class="flex-between">
          <span class="badge badge-${bidStatus.replace(' ', '-')}">${bidStatus}</span>
          ${bidStatus === 'in-progress' ? `
            <button class="btn btn-primary btn-sm" onclick="completeFreelancerProject(${bid.project_id})">
              ${project?.freelancer_completed ? '✓ Waiting for client' : 'Mark Complete'}
            </button>
          ` : ''}
        </div>
      </div>
    `);
  }

  container.innerHTML = bidCards.join('');
}

// --- Complete Project (Freelancer side) ---

async function completeFreelancerProject(projectId) {
  const res = await projectsAPI.complete(projectId);
  if (res.ok) {
    if (res.data.status === 'completed') {
      showToast('Project completed! 🎉', 'success');
    } else {
      showToast('Your confirmation recorded. Waiting for the client.', 'info');
    }
    loadMyBids();
    loadStats();
  } else {
    showToast(res.error, 'error');
  }
}

// --- Profile Update ---

function setupProfileForm() {
  const form = document.getElementById('profile-form');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const skillsRaw = document.getElementById('profile-skills').value;
    const skills = skillsRaw.split(',').map(s => s.trim()).filter(s => s);
    const hourlyRate = parseFloat(document.getElementById('profile-rate').value);

    const res = await freelancersAPI.updateProfile({ skills, hourly_rate: hourlyRate });
    if (res.ok) {
      currentProfile = res.data;
      renderProfileCard();
      showToast('Profile updated!', 'success');
      closeModal('profile-modal');
    } else {
      showToast(res.error, 'error');
    }
  });

  // Pre-fill when modal opens
  document.querySelector('[onclick*="profile-modal"]')?.addEventListener('click', () => {
    if (currentProfile) {
      document.getElementById('profile-skills').value = (currentProfile.skills || []).join(', ');
      document.getElementById('profile-rate').value = currentProfile.hourly_rate || '';
    }
  });
}

// --- Utility ---

function escapeHTML(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
