import { async, ComponentFixture } from '@angular/core/testing';
import { TestUtils } from '../../../test';
import { RegisterConfigureServicesComponent } from './register-configure-services';

let fixture: ComponentFixture<RegisterConfigureServicesComponent>;
let instance: any;

describe('Pages: RegisterConfigureServicesComponent', () => {

  beforeEach(async(() => TestUtils.beforeEachCompiler([RegisterConfigureServicesComponent])
    .then(compiled => {
      fixture = compiled.fixture;
      instance = compiled.instance;
    })));

  it('should create the RegisterConfigureServicesComponent', async(() => {
    expect(instance)
      .toBeTruthy();
  }));

  it('should have 2 services', async(() => {
    expect(instance.services)
      .toEqual(
        [
          { name: 'Haircut', price: 70 },
          { name: 'Nails', price: 30 }
        ]
      );
  }));

  it('should have navCtrl and navParams', async(() => {
    expect(instance.navCtrl)
      .toBeTruthy();

    expect(instance.navParams)
      .toBeTruthy();
  }));

});
