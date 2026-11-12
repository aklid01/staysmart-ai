import type { ReactNode } from 'react'

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = []
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g
  let lastIndex = 0
  let match: RegExpExecArray | null
  let index = 0
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index))
    }
    const token = match[0]
    if (token.startsWith('**')) {
      nodes.push(<strong key={`${keyPrefix}-b${index}`}>{token.slice(2, -2)}</strong>)
    } else {
      nodes.push(<code key={`${keyPrefix}-c${index}`}>{token.slice(1, -1)}</code>)
    }
    lastIndex = match.index + token.length
    index += 1
  }
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex))
  }
  return nodes
}

export function MarkdownLite({ text }: { text: string }) {
  const lines = text.split('\n')
  const blocks: ReactNode[] = []
  let paragraph: string[] = []
  let table: string[] = []
  let key = 0

  const flushParagraph = () => {
    if (paragraph.length > 0) {
      blocks.push(<p key={`p${key++}`}>{renderInline(paragraph.join(' '), `p${key}`)}</p>)
      paragraph = []
    }
  }
  const flushTable = () => {
    if (table.length > 1) {
      const rows = table
        .map((line) =>
          line
            .trim()
            .replace(/^\|/, '')
            .replace(/\|$/, '')
            .split('|')
            .map((cell) => cell.trim()),
        )
        .filter((cells) => !cells.every((cell) => /^-{2,}$/.test(cell) || cell === ''))
      if (rows.length > 0) {
        const [header, ...body] = rows
        blocks.push(
          <table key={`t${key++}`} className="md-table">
            <thead>
              <tr>
                {header.map((cell, i) => (
                  <th key={i}>{renderInline(cell, `th${key}-${i}`)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {body.map((cells, r) => (
                <tr key={r}>
                  {cells.map((cell, i) => (
                    <td key={i}>{renderInline(cell, `td${key}-${r}-${i}`)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>,
        )
      }
    }
    table = []
  }

  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('|')) {
      flushParagraph()
      table.push(line)
    } else if (trimmed === '') {
      flushParagraph()
      flushTable()
    } else if (/^#{1,4}\s/.test(trimmed)) {
      flushParagraph()
      flushTable()
      blocks.push(
        <strong key={`h${key++}`}>
          {renderInline(trimmed.replace(/^#{1,4}\s/, ''), `h${key}`)}
        </strong>,
      )
    } else {
      if (table.length > 0) {
        flushTable()
      }
      paragraph.push(trimmed)
    }
  }
  flushParagraph()
  flushTable()

  return <div className="markdown">{blocks}</div>
}
