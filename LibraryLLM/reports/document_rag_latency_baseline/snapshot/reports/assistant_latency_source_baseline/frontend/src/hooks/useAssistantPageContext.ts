import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { useAssistantStore } from '../store/useAssistantStore'
import type { AssistantPageContext } from '../lib/assistantTypes'
export function useAssistantPageContext(context: AssistantPageContext) {
  const { pathname, search } = useLocation()
  const key = pathname + search
  const serialized = JSON.stringify(context)
  useEffect(() => {
    useAssistantStore.getState().setPageContext(key, JSON.parse(serialized))
    return () => { if (useAssistantStore.getState().pagePath === key) useAssistantStore.getState().setPageContext('', {}) }
  }, [key, serialized])
}
