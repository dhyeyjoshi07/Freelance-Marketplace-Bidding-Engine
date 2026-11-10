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
  loadFreelancerData();
  loadOpenProjects();
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
        <h3>${escapeHTML(getUsername())}</h3>
        <p class="text-secondary text-sm">Freelancer</p>
      </div>
      <button class="btn btn-secondary btn-sm" onclick="openProfileModal()">Edit Profile</button>
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

function openProfileModal() {
  if (currentProfile) {
    document.getElementById('profile-skills').value = (currentProfile.skills || []).join(', ');
    document.getElementById('profile-rate').value = currentProfile.hourly_rate || '';
  }
  openModal('profile-modal');
}

// --- Project Cache & Batch Loading (Eliminates N+1 queries) ---

const projectCache = new Map();

async function getProjectsByIds(ids) {
  const missing = ids.filter(id => !projectCache.has(id));
  if (missing.length > 0) {
    const responses = await Promise.all(missing.map(id => projectsAPI.get(id)));
    responses.forEach((res, i) => {
      if (res.ok) projectCache.set(missing[i], res.data);
    });
  }
  return projectCache;
}

// --- Combined Stats & My Bids Loader ---

async function loadFreelancerData() {
  const container = document.getElementById('my-bids-list');
  if (container) {
    container.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';
  }

  const bidsRes = await bidsAPI.myBids();
  if (!bidsRes.ok) {
    if (container) {
      container.innerHTML = `<div class="empty-state"><p>${escapeHTML(bidsRes.error)}</p></div>`;
    }
    return;
  }

  const bids = bidsRes.data;
  const projectIds = [...new Set(bids.map(b => b.project_id))];

  // Batch fetch all required project records concurrently
  await getProjectsByIds(projectIds);

  renderStats(bids);
  renderMyBids(bids);
}

function renderStats(bids) {
  const elBids = document.getElementById('stat-bids');
  const elActive = document.getElementById('stat-active');
  const elCompleted = document.getElementById('stat-completed');
  const elEarned = document.getElementById('stat-earned');

  if (elBids) elBids.textContent = bids.length;

  let active = 0;
  let completed = 0;
  let earned = 0;

  for (const bid of bids) {
    const project = projectCache.get(bid.project_id);
    if (!project) continue;

    const isAccepted = project.accepted_bid_id === bid.id;
    if (isAccepted) {
      if (project.status === 'in_progress') {
        active++;
        earned += bid.amount;
      } else if (project.status === 'completed') {
        completed++;
        earned += bid.amount;
      }
    }
  }

  if (elActive) elActive.textContent = active;
  if (elCompleted) elCompleted.textContent = completed;
  if (elEarned) elEarned.textContent = formatCurrency(earned);
}

function renderMyBids(bids) {
  const container = document.getElementById('my-bids-list');
  if (!container) return;

  if (bids.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📝</div>
        <p>No bids yet. Browse open projects and submit your first bid!</p>
      </div>`;
    return;
  }

  const bidCards = bids.map((bid, i) => {
    const project = projectCache.get(bid.project_id);
    const isAccepted = project?.accepted_bid_id === bid.id;

    let bidStatus = 'pending';
    if (project?.status === 'completed' && isAccepted) bidStatus = 'completed';
    else if (project?.status === 'in_progress' && isAccepted) bidStatus = 'in-progress';
    else if (project?.status !== 'open' && !isAccepted) bidStatus = 'not selected';

    return `
      <div class="glass-card animate-in animate-in-delay-${Math.min(i, 4)}" style="padding: var(--space-lg);">
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
          <span class="badge badge-${escapeHTML(bidStatus.replace(/ /g, '-'))}">${escapeHTML(bidStatus)}</span>
          ${bidStatus === 'in-progress' ? `
            <button class="btn btn-primary btn-sm" id="btn-freelancer-complete-${bid.project_id}" onclick="completeFreelancerProject(${bid.project_id})">
              ${project?.freelancer_completed ? '✓ Waiting for client' : 'Mark Complete'}
            </button>
          ` : ''}
        </div>
      </div>
    `;
  });

  container.innerHTML = bidCards.join('');
}

// Wrapper for manual refresh button
async function loadMyBids() {
  await loadFreelancerData();
}

// --- Browse Open Projects ---

const openProjectsMap = new Map();

async function loadOpenProjects() {
  const container = document.getElementById('open-projects-list');
  container.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';

  const res = await projectsAPI.listAll();
  if (!res.ok) {
    container.innerHTML = `<div class="empty-state"><p>${escapeHTML(res.error)}</p></div>`;
    return;
  }

  const projects = res.data;
  openProjectsMap.clear();

  if (projects.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🔍</div>
        <p>No open projects at the moment. Check back soon!</p>
      </div>`;
    return;
  }

  container.innerHTML = projects.map((p, i) => {
    openProjectsMap.set(p.id, p);
    return `
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
          <button class="btn btn-primary btn-sm" onclick="openBidModalById(${p.id})">
            Submit Bid
          </button>
        </div>
      </div>
    `;
  }).join('');
}

// --- Submit Bid (Safe from JS injection) ---

let bidProjectId = null;

function openBidModalById(projectId) {
  const project = openProjectsMap.get(projectId);
  if (!project) return;

  bidProjectId = projectId;
  document.getElementById('bid-project-title').textContent = project.title;
  document.getElementById('bid-budget-range').textContent =
    `${formatCurrency(project.budget_min)} – ${formatCurrency(project.budget_max)}`;
  openModal('bid-modal');
}

function setupBidForm() {
  const form = document.getElementById('bid-form');
  const submitBtn = form.querySelector('button[type="submit"]');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const amount = parseFloat(document.getElementById('bid-amount').value);
    const proposal = document.getElementById('bid-proposal').value;

    if (isNaN(amount) || amount <= 0) {
      showToast('Please enter a valid positive bid amount', 'error');
      return;
    }

    const body = { amount, proposal };

    submitBtn.disabled = true;
    submitBtn.classList.add('btn-loading');

    try {
      const res = await bidsAPI.submit(bidProjectId, body);
      if (res.ok) {
        showToast(`Bid submitted! Match score: ${Math.round(res.data.match_score * 100)}%`, 'success');
        closeModal('bid-modal');
        form.reset();
        await Promise.all([
          loadOpenProjects(),
          loadFreelancerData(),
        ]);
      } else {
        showToast(res.error, 'error');
      }
    } finally {
      submitBtn.disabled = false;
      submitBtn.classList.remove('btn-loading');
    }
  });
}

// --- Complete Project (Freelancer side) ---

async function completeFreelancerProject(projectId) {
  const btn = document.getElementById(`btn-freelancer-complete-${projectId}`);
  if (btn) {
    btn.disabled = true;
    btn.classList.add('btn-loading');
  }

  try {
    const res = await projectsAPI.complete(projectId);
    if (res.ok) {
      if (res.data.status === 'completed') {
        showToast('Project completed! 🎉', 'success');
      } else {
        showToast('Your confirmation recorded. Waiting for the client.', 'info');
      }
      projectCache.delete(projectId); // Invalidate cache for this project
      await loadFreelancerData();
    } else {
      showToast(res.error, 'error');
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.classList.remove('btn-loading');
    }
  }
}

// --- Profile Update ---

function setupProfileForm() {
  const form = document.getElementById('profile-form');
  const submitBtn = form.querySelector('button[type="submit"]');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const skillsRaw = document.getElementById('profile-skills').value;
    const skills = skillsRaw.split(',').map(s => s.trim()).filter(s => s);
    const hourlyRate = parseFloat(document.getElementById('profile-rate').value);

    if (isNaN(hourlyRate) || hourlyRate <= 0) {
      showToast('Please enter a valid positive hourly rate', 'error');
      return;
    }

    submitBtn.disabled = true;
    submitBtn.classList.add('btn-loading');

    try {
      const res = await freelancersAPI.updateProfile({ skills, hourly_rate: hourlyRate });
      if (res.ok) {
        currentProfile = res.data;
        renderProfileCard();
        showToast('Profile updated!', 'success');
        closeModal('profile-modal');
      } else {
        showToast(res.error, 'error');
      }
    } finally {
      submitBtn.disabled = false;
      submitBtn.classList.remove('btn-loading');
    }
  });
}
