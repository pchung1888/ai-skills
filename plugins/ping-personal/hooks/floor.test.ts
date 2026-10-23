import { test, expect } from 'claude-code/testing'
import { floorReason, normTarget } from './hud-floor'

// Commands are built from words so no test file spells a destructive command in one piece.
const c = (...w: string[]) => w.join(' ')
const bash = (...w: string[]) => floorReason('Bash', { command: c(...w) }, ['D:\\playground\\repo', 'D:/playground/repo'])
const ps = (...w: string[]) => floorReason('PowerShell', { command: c(...w) }, ['D:\\playground\\repo'])
const R = '-' + 'rf'

test('denied: recursive delete of a root, a drive, home, the current or parent folder, a wildcard', () => {
  for (const t of ['/', '/*', '~', '~/', '$HOME', '.', './', '..', '*', 'C:/', 'C:\\', '/c', '/d/', '"/"'])
    expect(bash('rm', R, t)).toBeDefined()
  expect(bash('rm', '-r', '-f', '/')).toBeDefined()
  expect(bash('rm', '--recursive', '~')).toBeDefined()
  expect(bash('ls', '&&', 'rm', R, '/')).toBeDefined() // later segment of a chain
  expect(ps('Remove-Item', '-Recurse', '-Force', 'C:\\')).toBeDefined()
  expect(ps('Remove-Item', '-Path', 'D:\\', '-r')).toBeDefined()
  expect(ps('rd', '/s', '/q', 'C:\\')).toBeDefined()
})

test('denied: deleting the repo, a folder above it, .git or Claude itself', () => {
  expect(bash('rm', R, 'D:/playground/repo')).toContain('repo')
  expect(bash('rm', R, '/d/playground')).toContain('above') // Git Bash path of a parent folder
  expect(ps('Remove-Item', '-Recurse', '"D:\\playground\\repo\\"')).toBeDefined()
  expect(bash('rm', R, '.git')).toContain('.git')
  expect(bash('rm', R, '~/.claude')).toContain('.claude')
  expect(ps('Remove-Item', '-Recurse', '$HOME\\.claude')).toBeDefined()
  expect(bash('npm', 'uninstall', '-g', '@anthropic-ai/claude-code')).toContain('Claude')
  expect(bash('gh', 'repo', 'delete', 'me/x', '--yes')).toBeDefined()
  expect(bash('git', 'push', '--force', 'origin', 'main')).toBeDefined()
  expect(bash('git', 'push', 'origin', '+main')).toBeDefined()
  expect(bash('git', 'push', 'origin', '--delete', 'main')).toBeDefined()
})

test('denied: formatting or wiping a disk', () => {
  expect(ps('Format-Volume', '-DriveLetter', 'D')).toBeDefined()
  expect(ps('format', 'D:')).toBeDefined()
  expect(ps('diskpart')).toBeDefined()
  expect(bash('dd', 'if=/dev/zero', 'of=/dev/sda')).toBeDefined()
})

test('allowed: ordinary deletes and pushes inside the repo, and other tools', () => {
  expect(bash('rm', R, 'node_modules')).toBeUndefined()
  expect(bash('rm', R, 'D:/playground/repo/build')).toBeUndefined() // below the repo root
  expect(bash('rm', 'file.txt')).toBeUndefined() // not recursive
  expect(bash('rm', R, '.claude/tmp')).toBeUndefined()
  expect(ps('Remove-Item', '-Recurse', 'docs\\progress')).toBeUndefined()
  expect(ps('Remove-Item', 'C:\\')).toBeUndefined() // not recursive: fails on its own
  expect(bash('git', 'push', 'origin', 'topic/x')).toBeUndefined()
  expect(bash('npm', 'uninstall', 'left-pad')).toBeUndefined()
  expect(bash('echo', 'format')).toBeUndefined() // a word in an argument, not the command
  expect(floorReason('Write', { file_path: '/' })).toBeUndefined()
  expect(floorReason('Bash', null)).toBeUndefined()
})

test('normTarget: one shape for every path style', () => {
  expect(normTarget('"D:\\Playground\\"')).toBe('d:/playground')
  expect(normTarget('/d/playground')).toBe('d:/playground')
  expect(normTarget('/*')).toBe('/')
  expect(normTarget('C:\\')).toBe('c:')
})
