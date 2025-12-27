/**
 * Manual UI test for Provider Settings
 * This test launches the Electron app and interacts with the provider UI
 *
 * Run: npx playwright test provider-ui-manual.test.ts --config=e2e/playwright.config.ts --headed
 */
import { test, expect, _electron as electron } from '@playwright/test';
import path from 'path';
import { existsSync, writeFileSync, mkdirSync } from 'fs';

const SCREENSHOT_DIR = path.join(__dirname, '../test-results/provider-ui-screenshots');

test.describe('Provider UI Manual Test', () => {
  test('should launch app and test provider settings UI', async () => {
    // Create screenshot directory
    if (!existsSync(SCREENSHOT_DIR)) {
      mkdirSync(SCREENSHOT_DIR, { recursive: true });
    }

    // Launch Electron app
    const electronApp = await electron.launch({
      args: [path.join(__dirname, '..')],
      env: {
        ...process.env,
        NODE_ENV: 'development'
      }
    });

    // Get the first window
    const window = await electronApp.firstWindow();
    await window.waitForLoadState('domcontentloaded');

    // Take screenshot of main app
    await window.screenshot({
      path: path.join(SCREENSHOT_DIR, '01-app-loaded.png'),
      fullPage: true
    });
    console.log('✅ Screenshot: App loaded');

    // Wait for app to fully render
    await window.waitForTimeout(2000);

    // Find and click settings button
    // Try multiple selectors for the settings button
    const settingsButton = await window.locator('button[aria-label*="Settings"], button:has-text("Settings"), [data-testid="settings-button"], button:has(svg)').first();

    if (await settingsButton.isVisible({ timeout: 5000 })) {
      await settingsButton.click();
      console.log('✅ Clicked settings button');
      await window.waitForTimeout(1000);

      await window.screenshot({
        path: path.join(SCREENSHOT_DIR, '02-settings-opened.png'),
        fullPage: true
      });
      console.log('✅ Screenshot: Settings dialog opened');

      // Look for project section
      const projectSection = await window.locator('text=/Project/i, h3:has-text("Project"), [data-section="project"]').first();

      if (await projectSection.isVisible({ timeout: 3000 })) {
        console.log('✅ Found Project section');

        // Look for Agent Provider tab/button
        const providerTab = await window.locator('text=/Agent Provider/i, button:has-text("Agent Provider"), [data-tab="provider"]').first();

        if (await providerTab.isVisible({ timeout: 3000 })) {
          await providerTab.click();
          console.log('✅ Clicked Agent Provider tab');
          await window.waitForTimeout(1000);

          await window.screenshot({
            path: path.join(SCREENSHOT_DIR, '03-provider-section.png'),
            fullPage: true
          });
          console.log('✅ Screenshot: Provider section opened');

          // Check for provider elements
          const checks = {
            'Agent Provider dropdown': await window.locator('select, [role="combobox"], text=/Claude Code|OpenCode/i').first().isVisible({ timeout: 2000 }).catch(() => false),
            'Provider status badge': await window.locator('[class*="badge"], [class*="status"]').first().isVisible({ timeout: 2000 }).catch(() => false),
            'Settings description': await window.locator('text=/Configure which AI provider/i').first().isVisible({ timeout: 2000 }).catch(() => false),
          };

          console.log('\n=== Provider UI Elements ===');
          for (const [name, visible] of Object.entries(checks)) {
            console.log(`${visible ? '✅' : '❌'} ${name}`);
          }
          console.log('===========================\n');

          // Try to interact with provider dropdown
          const providerDropdown = await window.locator('select, [role="combobox"]').first();
          if (await providerDropdown.isVisible({ timeout: 2000 })) {
            console.log('✅ Found provider dropdown');

            await window.screenshot({
              path: path.join(SCREENSHOT_DIR, '04-provider-dropdown-found.png'),
              fullPage: true
            });
            console.log('✅ Screenshot: Provider dropdown visible');

            // Try to get dropdown options
            try {
              const options = await window.locator('select option, [role="option"]').allTextContents();
              console.log('📋 Available providers:', options);
            } catch (e) {
              console.log('⚠️  Could not get dropdown options');
            }
          }

        } else {
          console.log('⚠️  Agent Provider tab not found');

          // Log all visible text to help debug
          const allButtons = await window.locator('button').allTextContents();
          console.log('📋 All buttons:', allButtons.slice(0, 20));
        }

      } else {
        console.log('⚠️  Project section not found');
      }

      // Take final screenshot
      await window.screenshot({
        path: path.join(SCREENSHOT_DIR, '05-final-state.png'),
        fullPage: true
      });
      console.log('✅ Screenshot: Final state');

    } else {
      console.log('⚠️  Settings button not found');

      // Take screenshot to see what's visible
      await window.screenshot({
        path: path.join(SCREENSHOT_DIR, 'error-no-settings-button.png'),
        fullPage: true
      });

      // Log all buttons for debugging
      const allButtons = await window.locator('button').allTextContents();
      console.log('📋 All visible buttons:', allButtons);
    }

    // Keep window open for manual inspection (optional)
    // await window.waitForTimeout(30000);

    await electronApp.close();

    console.log('\n✅ Test completed successfully!');
    console.log(`📸 Screenshots saved to: ${SCREENSHOT_DIR}`);
  });
});
