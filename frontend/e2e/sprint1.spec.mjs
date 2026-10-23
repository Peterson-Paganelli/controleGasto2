import { test, expect } from '@playwright/test'

// Confere se os controles cabem na tela e podem ser usados com o teclado.
async function verificarTela(page, nome, testInfo) {
  const largura = page.viewportSize().width
  const larguraConteudo = await page.evaluate(() => document.documentElement.scrollWidth)
  expect(larguraConteudo).toBeLessThanOrEqual(largura)

  for (const controle of await page.locator('input, button, a').all()) {
    await controle.scrollIntoViewIfNeeded()
    await expect(controle).toBeVisible()
    await expect(controle).toBeEnabled()
    const caixa = await controle.boundingBox()
    expect(caixa.x).toBeGreaterThanOrEqual(0)
    expect(caixa.x + caixa.width).toBeLessThanOrEqual(largura)
    await controle.focus()
    await expect(controle).toBeFocused()
  }

  await page.screenshot({ path: testInfo.outputPath(`${nome}.png`), fullPage: true })
}

test('cadastrar, entrar e sair da conta', async ({ page }, testInfo) => {
  // Cada execução cria uma conta diferente no banco de testes.
  const numero = Date.now().toString().slice(-11)
  const nome = 'Pessoa de teste com nome completo longo para conferir a tela'
  const email = `teste${numero}@sprint1.example.com`
  const senha = 'Senha-de-teste-123'
  const erros = []

  page.on('pageerror', erro => erros.push(erro.message))
  page.on('response', resposta => {
    if (resposta.status() >= 500) erros.push(`${resposta.status()} ${resposta.url()}`)
  })

  // 1. Sem login, a área interna deve redirecionar para a tela de entrada.
  await page.goto('/app')
  await expect(page).toHaveURL(/\/login$/)
  await verificarTela(page, 'login', testInfo)

  // 2. Cadastra uma conta pelo formulário real.
  await page.getByRole('button', { name: 'Criar conta', exact: true }).click()
  await page.getByLabel('Nome completo').fill(nome)
  await page.getByLabel('CPF', { exact: true }).fill(numero)
  await page.getByLabel('Telefone com DDD').fill(numero)
  await page.getByLabel('E-mail').fill(email)
  await page.getByLabel('Senha', { exact: true }).fill(senha)
  await verificarTela(page, 'cadastro', testInfo)
  await page.locator('form').getByRole('button', { name: 'Criar conta' }).click()
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('status')).toContainText('Cadastro realizado!')

  // 3. Uma senha errada não pode permitir a entrada.
  await page.getByLabel('Senha', { exact: true }).fill('senha-incorreta')
  await page.getByRole('button', { name: 'Entrar na conta' }).click()
  await expect(page.getByRole('alert')).toHaveText('E-mail ou senha inválidos.')

  // 4. A senha correta abre a área interna e mostra os dados da conta.
  await page.getByLabel('E-mail').fill(email)
  await page.getByLabel('Senha', { exact: true }).fill(senha)
  await page.getByRole('button', { name: 'Entrar na conta' }).click()
  await expect(page).toHaveURL(/\/app$/)
  await expect(page.getByRole('heading', { name: `Olá, ${nome}!` })).toBeVisible()
  await expect(page.locator('.email-usuario')).toHaveText(email)
  await verificarTela(page, 'area-interna', testInfo)

  // 5. Depois de sair, voltar ou abrir /app não deve liberar a conta.
  await page.getByRole('button', { name: 'Sair da conta' }).click()
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('status')).toHaveText('Você saiu da conta.')
  await page.goBack()
  await expect(page).toHaveURL(/\/login$/)
  await page.goto('/app')
  await expect(page).toHaveURL(/\/login$/)
  expect(erros).toEqual([])
})
