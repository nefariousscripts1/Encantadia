"""Static acceptance checks for the separated Map and Cipher workspace."""

from pathlib import Path
import unittest

from app import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SeparatedWorkspaceUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        with cls.app.test_client() as client:
            response = client.get("/")
        cls.html = response.data.decode("utf-8")
        cls.javascript = (PROJECT_ROOT / "app" / "static" / "js" / "app.js").read_text(
            encoding="utf-8"
        )

    def test_page_and_cipher_tabs_have_distinct_panels_and_controls(self):
        self.assertNotIn("Map Online", self.html)
        self.assertNotIn('id="mapStatus"', self.html)
        for element_id in (
            "mapPageTab",
            "cipherPageTab",
            "mapPagePanel",
            "cipherPagePanel",
            "encryptTab",
            "decryptTab",
            "encryptPanel",
            "decryptPanel",
            "downloadRouteButton",
            "mapCipherKey",
            "mapCipherKeyValue",
            "routeMetricVisited",
            "routeVisitedNodesDisplay",
            "encryptFileInput",
            "encryptFileName",
            "encryptTextInput",
            "encryptCipherKey",
            "encryptButton",
            "encryptOutput",
            "copyCiphertextButton",
            "downloadEncryptedButton",
            "useInDecryptButton",
            "decryptFileInput",
            "decryptFileName",
            "decryptTextInput",
            "decryptCipherKey",
            "decryptButton",
            "decryptOutput",
            "copyDecryptedButton",
            "downloadDecryptedButton",
        ):
            with self.subTest(element_id=element_id):
                self.assertEqual(self.html.count(f'id="{element_id}"'), 1)

        map_markup = self.html.split('id="mapPagePanel"', 1)[1].split(
            'id="cipherPagePanel"', 1
        )[0]
        for legacy_id in (
            "cipherKey",
            "encryptedExport",
            "decryptedVerificationBox",
            "encryptionStatus",
            "downloadButton",
        ):
            self.assertNotIn(f'id="{legacy_id}"', map_markup)
        self.assertIn("Caesar Shift Key", map_markup)
        self.assertIn("Ciphertext preview:", map_markup)
        self.assertNotIn('id="encryptFileInput"', map_markup)
        self.assertNotIn('id="decryptFileInput"', map_markup)

    def test_javascript_keeps_astar_shift_free_and_encrypts_map_export(self):
        astar_function = self.javascript[
            self.javascript.index("async function requestAStar") : self.javascript.index(
                "async function runAStar"
            )
        ]
        self.assertIn('fetch("/api/astar"', astar_function)
        self.assertNotIn("shift", astar_function)
        self.assertIn("async function refreshMapEncryption", self.javascript)
        self.assertIn("mapCiphertextResult", self.javascript)
        self.assertIn('postJson("/api/encrypt"', self.javascript)
        self.assertIn('downloadTextFile(filename, `Ciphertext:', self.javascript)
        self.assertIn('postJson("/api/encrypt-text"', self.javascript)
        self.assertIn('postJson("/api/decrypt-text"', self.javascript)
        self.assertIn("cipherState.encrypt", self.javascript)
        self.assertIn("cipherState.decrypt", self.javascript)
        self.assertIn("useCiphertextInDecrypt", self.javascript)
        self.assertIn("URL.revokeObjectURL", self.javascript)
        self.assertIn('accept=".txt,text/plain"', self.html)
        self.assertIn('placeholder="Enter text to encrypt..."', self.html)

    def test_uploads_only_select_files_and_actions_are_explicit(self):
        selection_function = self.javascript[
            self.javascript.index("function selectCipherFile") : self.javascript.index(
                "function clearSelectedCipherFile"
            )
        ]
        source_function = self.javascript[
            self.javascript.index("async function resolveCipherSource") : self.javascript.index(
                "async function runEncrypt"
            )
        ]
        encrypt_function = self.javascript[
            self.javascript.index("async function runEncrypt") : self.javascript.index(
                "async function runDecrypt"
            )
        ]
        decrypt_function = self.javascript[
            self.javascript.index("async function runDecrypt") : self.javascript.index(
                "function useCiphertextInDecrypt"
            )
        ]
        transfer_function = self.javascript[
            self.javascript.index("function useCiphertextInDecrypt") : self.javascript.index(
                "function handleCipherTextInput"
            )
        ]

        self.assertNotIn("state.file.text()", selection_function)
        self.assertNotIn("postJson(", selection_function)
        self.assertIn("const content = await state.file.text()", source_function)
        self.assertIn("postJson(\"/api/encrypt-text\"", encrypt_function)
        self.assertIn("postJson(\"/api/decrypt-text\"", decrypt_function)
        self.assertIn('if (state.busy) return;', encrypt_function)
        self.assertIn('if (state.busy) return;', decrypt_function)
        self.assertIn('if (input) input.value = "";', selection_function)
        self.assertIn("decryptTextInput.value = result.ciphertext", transfer_function)
        self.assertIn("decryptCipherKey.value = String(result.shift)", transfer_function)
        self.assertIn("showDecryptPanel()", transfer_function)
        self.assertNotIn("runDecrypt()", transfer_function)
        self.assertIn('id="runButton" class="btn btn-primary btn-action-main" type="button" disabled', self.html)
        self.assertIn("routeDownloadBusy", self.javascript)
        self.assertIn("downloadBusy", self.javascript)
        self.assertIn("bindTabKeyboard", self.javascript)
        self.assertIn('event.key === "ArrowRight"', self.javascript)


if __name__ == "__main__":
    unittest.main()
