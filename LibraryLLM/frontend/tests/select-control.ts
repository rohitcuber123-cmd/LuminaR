/** Exercise the visible menu, while retaining native assessment control support. */
export function chooseSelect(control: HTMLElement, value: string, fireEvent: any) {
  if (control.tagName !== 'BUTTON' || control.getAttribute('role') !== 'combobox') {
    fireEvent.change(control, { target: { value } }); return
  }
  if (control.getAttribute('aria-expanded') !== 'true') fireEvent.click(control)
  const bridge = document.getElementById(`${control.id}-native`) as HTMLSelectElement
  const label = [...bridge.options].find(option => option.value === value)?.textContent
  const list = document.getElementById(control.getAttribute('aria-controls')!)
  const option = [...list!.querySelectorAll('[role="option"]')].find(option => option.textContent === label)
  if (!option) throw new Error(`No selectable option for ${value}`)
  fireEvent.click(option)
}
export function selectedValue(control: HTMLElement) {
  if (control.tagName === 'SELECT') return (control as HTMLSelectElement).value
  const bridge=document.getElementById(`${control.id}-native`) as HTMLSelectElement
  const selected=bridge.selectedOptions[0]
  if (selected && !control.textContent?.includes(selected.textContent || '')) throw new Error('Visible selection and submitted value disagree')
  return bridge.value
}
