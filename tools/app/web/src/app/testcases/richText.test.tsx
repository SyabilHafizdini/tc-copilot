import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { RichText } from './richText'

describe('RichText', () => {
  it('renders **markers** as bold and keeps the rest as text', () => {
    const { container } = render(<RichText text={'1. Click **Save** then **Ok**.'} />)
    const bold = [...container.querySelectorAll('strong')].map((b) => b.textContent)
    expect(bold).toEqual(['Save', 'Ok'])
    expect(container.textContent).toBe('1. Click Save then Ok.')
  })

  it('keeps line breaks and indentation for pre-wrap rendering', () => {
    const text = '2. Elements:\n    a. Button : **Go**\n\n3. Done.'
    const { container } = render(<RichText text={text} />)
    expect(container.querySelector('.rich-text')).not.toBeNull()
    expect(container.textContent).toBe('2. Elements:\n    a. Button : Go\n\n3. Done.')
  })

  it('shows em and en dashes as hyphens, like the workbook', () => {
    const { container } = render(<RichText text={'A — B – C'} />)
    expect(container.textContent).toBe('A - B - C')
  })

  it('leaves an unmatched marker and an empty string alone', () => {
    expect(render(<RichText text={'2 ** 3'} />).container.textContent).toBe('2 ** 3')
    expect(render(<RichText text="" />).container.textContent).toBe('')
  })
})
