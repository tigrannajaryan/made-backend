import { ComponentFixture, async, TestBed } from '@angular/core/testing';
import { TestUtils } from '../../test';
import { LoginPage } from './login';
import { AuthServiceProvider } from '../../providers/auth-service/auth-service';

let fixture: ComponentFixture<LoginPage> = null;
let instance: LoginPage = null;

describe('Pages: LoginPage', () => {

  beforeEach(async(() => TestUtils.beforeEachCompiler([LoginPage]).then(compiled => {
    fixture = compiled.fixture;
    instance = compiled.instance;
  })));

  it('should create the page', async(() => {
    expect(instance).toBeTruthy();
  }));

  it('should authenticate after login is called with valid credentials', async(() => {

    const authService = TestBed.get(AuthServiceProvider);

    expect(authService.getAuthToken()).toEqual(null);

    instance.formData.email = "user@test.com";
    instance.formData.password = "pass123";

    instance.login().
      then(() => {
        expect(authService.getAuthToken()).toEqual('test-token');
      });
  }));

  it('should fail to authenticate after login is called with wrong password', async(() => {

    const authService = TestBed.get(AuthServiceProvider);

    expect(authService.getAuthToken()).toEqual(null);

    instance.formData.email = "user@test.com";
    instance.formData.password = "wrongpassword";

    instance.login().
      then(() => {
        expect(authService.getAuthToken()).toEqual(null);
      });
  }));
});