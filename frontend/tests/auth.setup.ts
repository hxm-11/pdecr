import { test as setup } from "@playwright/test"
import { firstSuperuser, firstSuperuserPassword } from "./config.ts"

const authFile = "playwright/.auth/user.json"

setup("authenticate", async ({ page }) => {
  await page.route("**/api/v1/login/access-token", async (route) => {
    await route.fulfill({
      json: {
        access_token: "playwright-test-token",
        token_type: "bearer",
      },
    })
  })

  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      json: {
        email: firstSuperuser,
        full_name: "Playwright Test User",
        id: "playwright-test-user",
        is_active: true,
        is_superuser: true,
      },
    })
  })

  await page.goto("/login")
  await page.getByTestId("email-input").fill(firstSuperuser)
  await page.getByTestId("password-input").fill(firstSuperuserPassword)
  await page.getByRole("button", { name: "Log In" }).click()
  await page.waitForURL("/")
  await page.context().storageState({ path: authFile })
})
