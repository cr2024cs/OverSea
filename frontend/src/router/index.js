import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue')
    },
    {
      path: '/',
      name: 'home',
      component: () => import('../views/ProjectListView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/projects/:projectId',
      name: 'chat',
      component: () => import('../views/ChatView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/lawyer',
      name: 'lawyer',
      component: () => import('../views/LawyerView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('../views/AdminView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/provider',
      name: 'provider',
      component: () => import('../views/ProviderView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/expert',
      name: 'expert',
      component: () => import('../views/ExpertView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/link/:token',
      name: 'requirement-link',
      component: () => import('../views/RequirementLinkView.vue')
    },
    {
      path: '/proposal-link/:token',
      name: 'proposal-link',
      component: () => import('../views/ProposalLinkView.vue')
    },
    {
      path: '/selection-link/:token',
      name: 'selection-link',
      component: () => import('../views/SelectionLinkView.vue')
    },
    {
      path: '/rfp-link/:token',
      name: 'rfp-link',
      component: () => import('../views/RfpLinkView.vue')
    },
    {
      path: '/client-quote-link/:token',
      name: 'client-quote-link',
      component: () => import('../views/ClientQuoteLinkView.vue')
    },
    {
      path: '/contract-link/:token',
      name: 'contract-link',
      component: () => import('../views/ContractLinkView.vue')
    },
    {
      path: '/expert-link/:token',
      name: 'expert-link',
      component: () => import('../views/ExpertLinkView.vue')
    },
    {
      path: '/query-link/:token',
      name: 'query-link',
      component: () => import('../views/QueryLinkView.vue')
    }
  ]
})

function storedUser() {
  try {
    return JSON.parse(localStorage.getItem('oversea_user') || 'null')
  } catch {
    return null
  }
}

function homeFor(user) {
  if (user?.role === 'admin') return { name: 'admin' }
  if (user?.role === 'lawyer') return { name: 'lawyer' }
  if (user?.role === 'provider') return { name: 'provider' }
  if (user?.role === 'expert') return { name: 'expert' }
  return { name: 'home' }
}

router.beforeEach((to) => {
  const token = localStorage.getItem('oversea_token')
  const user = storedUser()

  if (to.meta.requiresAuth && !token) {
    return { name: 'login' }
  }
  if (to.name === 'login' && token) {
    return homeFor(user)
  }
  if (to.name === 'home' && ['admin', 'lawyer', 'provider', 'expert'].includes(user?.role)) {
    return homeFor(user)
  }
  if (to.name === 'admin' && user?.role !== 'admin') {
    return homeFor(user)
  }
  if (to.name === 'lawyer' && user?.role !== 'lawyer') {
    return homeFor(user)
  }
  if (to.name === 'provider' && user?.role !== 'provider') {
    return homeFor(user)
  }
  if (to.name === 'expert' && user?.role !== 'expert') {
    return homeFor(user)
  }
  if (to.name === 'chat' && ['provider', 'expert'].includes(user?.role)) {
    return homeFor(user)
  }
  return true
})

export default router
